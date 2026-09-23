"""Сценарий записи клиента.

Порядок состояний соответствует ТЗ: дата -> время (базовая часовая сетка) ->
услуга -> данные клиента -> подтверждение. Время выбирается ДО услуги на базовой
часовой сетке; когда услуга требует больше одного часа, доступность нужного числа
последовательных слотов перепроверяется сразу после выбора услуги и ещё раз атомарно
в момент подтверждения (services/booking_service.py) — если её не хватает, пользователь
возвращается к выбору времени с понятным сообщением (защита от гонок, п.9 ТЗ)."""
from __future__ import annotations

from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, ReplyKeyboardRemove

from config import ADMIN_ID, SCHEDULE_DAYS_AHEAD, SERVICES_BY_KEY
from database import queries
from handlers.start import welcome_text
from keyboards.booking import (
    ActiveBookingAction,
    CancelFSM,
    ConfirmAction,
    ServiceCallback,
    SkipField,
    TimeCallback,
    active_booking_conflict_kb,
    cancel_fsm_kb,
    confirm_booking_kb,
    my_booking_cancel_confirm_kb,
    phone_request_kb,
    service_list_kb,
    skip_kb,
    time_slots_kb,
)
from keyboards.calendar import CalendarDay, CalendarNav, build_calendar
from keyboards.main import MenuAction, back_to_menu_kb, main_menu_kb
from services.booking_service import BookingError, create_booking
from services.notification_service import notify_admin_new_booking, notify_channel_new_booking
from services.reminder_service import schedule_reminder
from services.schedule_service import get_available_start_times
from states.booking import BookingStates
from utils.formatters import format_booking_summary, format_date_human
from utils.validators import is_valid_free_text, is_valid_name, is_valid_phone, normalize_phone

router = Router(name="booking")

BOOK_MODE = "book_date"


def _date_range() -> tuple[date, date]:
    today = date.today()
    return today, today + timedelta(days=SCHEDULE_DAYS_AHEAD - 1)


async def _calendar_view(year: int, month: int, prefix: str = "") -> tuple[str, InlineKeyboardMarkup]:
    min_date, max_date = _date_range()
    dates = await queries.get_dates_with_available_slots(min_date, max_date)
    highlighted = {d.isoformat() for d in dates}
    closed = {d.isoformat() for d in await queries.get_closed_dates(min_date, max_date)}
    kb = build_calendar(
        year, month, mode=BOOK_MODE, min_date=min_date, max_date=max_date,
        highlighted_dates=highlighted, closed_dates=closed, only_highlighted_clickable=True,
    )
    text = prefix + "📅 Выберите дату записи (отмечены дни со свободным временем):"
    return text, kb


async def _render_calendar(callback: CallbackQuery, year: int, month: int, prefix: str = "") -> None:
    text, kb = await _calendar_view(year, month, prefix)
    await callback.message.edit_text(text, reply_markup=kb)


async def _slot_still_available(target_date: date, start_time: str, duration_hours: int) -> bool:
    available = await get_available_start_times(target_date, duration_hours)
    return start_time in available


async def _reject_slot_taken(callback: CallbackQuery, state: FSMContext, target_date: date) -> None:
    reject_text = "❌ К сожалению, выбранное время уже заняли.\n\nПожалуйста, выберите другое время."
    times = await get_available_start_times(target_date, duration_hours=1)
    if times:
        await state.set_state(BookingStates.select_time)
        await callback.message.edit_text(
            f"{reject_text}\n\n📅 {format_date_human(target_date)}", reply_markup=time_slots_kb(times)
        )
    else:
        await state.set_state(BookingStates.select_date)
        today = date.today()
        await _render_calendar(callback, today.year, today.month, prefix=reject_text + "\n\n")


async def _start_booking(callback: CallbackQuery, state: FSMContext) -> None:
    existing = await queries.get_active_booking_for_telegram_id(callback.from_user.id)
    if existing is not None:
        text = (
            "📋 У вас уже есть активная запись:\n\n"
            f"📅 {format_date_human(existing.date)}\n"
            f"🕐 {existing.start_time}\n\n"
            f"🚗 {existing.car_brand} {existing.car_model}\n"
            f"🔧 {existing.service}"
        )
        await callback.message.edit_text(text, reply_markup=active_booking_conflict_kb())
        await callback.answer()
        return

    await state.set_state(BookingStates.select_date)
    today = date.today()
    await _render_calendar(callback, today.year, today.month)
    await callback.answer()


@router.callback_query(MenuAction.filter(F.action == "book"))
async def cb_book(callback: CallbackQuery, state: FSMContext) -> None:
    await _start_booking(callback, state)


@router.callback_query(ActiveBookingAction.filter(F.action == "view"))
async def cb_active_view(callback: CallbackQuery) -> None:
    from handlers.profile import render_my_booking

    await render_my_booking(callback)
    await callback.answer()


@router.callback_query(ActiveBookingAction.filter(F.action == "cancel"))
async def cb_active_cancel(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Вы действительно хотите отменить запись?", reply_markup=my_booking_cancel_confirm_kb()
    )
    await callback.answer()


@router.callback_query(ActiveBookingAction.filter(F.action == "back"))
async def cb_active_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(welcome_text(), reply_markup=main_menu_kb(callback.from_user.id == ADMIN_ID))
    await callback.answer()


@router.callback_query(CancelFSM.filter())
async def cb_cancel_fsm(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(welcome_text(), reply_markup=main_menu_kb(callback.from_user.id == ADMIN_ID))
    await callback.answer("Отменено")


async def _cancel_fsm_via_message(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=ReplyKeyboardRemove())
    await message.answer(welcome_text(), reply_markup=main_menu_kb(message.from_user.id == ADMIN_ID))


# --- Дата ---------------------------------------------------------------------

@router.callback_query(CalendarNav.filter(F.mode == BOOK_MODE), StateFilter(BookingStates.select_date))
async def cb_calendar_nav(callback: CallbackQuery, callback_data: CalendarNav) -> None:
    await _render_calendar(callback, callback_data.year, callback_data.month)
    await callback.answer()


@router.callback_query(CalendarDay.filter(F.mode == BOOK_MODE), StateFilter(BookingStates.select_date))
async def cb_calendar_day(callback: CallbackQuery, callback_data: CalendarDay, state: FSMContext) -> None:
    chosen_date = date.fromisoformat(callback_data.date)

    if await queries.is_day_closed(chosen_date):
        await callback.answer("Этот день закрыт для записи.", show_alert=True)
        return

    times = await get_available_start_times(chosen_date, duration_hours=1)
    if not times:
        await callback.answer("На эту дату уже не осталось свободного времени 🙁", show_alert=True)
        return

    await state.update_data(date=callback_data.date)
    await state.set_state(BookingStates.select_time)
    await callback.message.edit_text(
        f"📅 {format_date_human(chosen_date)}\n\nВыберите удобное время:", reply_markup=time_slots_kb(times)
    )
    await callback.answer()


# --- Время --------------------------------------------------------------------

@router.callback_query(TimeCallback.filter(), StateFilter(BookingStates.select_time))
async def cb_choose_time(callback: CallbackQuery, callback_data: TimeCallback, state: FSMContext) -> None:
    data = await state.get_data()
    chosen_date = date.fromisoformat(data["date"])

    times = await get_available_start_times(chosen_date, duration_hours=1)
    if callback_data.time not in times:
        await callback.answer("Это время уже заняли, выберите другое 🙁", show_alert=True)
        if times:
            await callback.message.edit_text(
                f"📅 {format_date_human(chosen_date)}\n\nВыберите удобное время:", reply_markup=time_slots_kb(times)
            )
        else:
            await state.set_state(BookingStates.select_date)
            today = date.today()
            await _render_calendar(callback, today.year, today.month)
        return

    await state.update_data(time=callback_data.time)
    await state.set_state(BookingStates.select_service)
    await callback.message.edit_text("🔧 Выберите услугу:", reply_markup=service_list_kb())
    await callback.answer()


# --- Услуга ---------------------------------------------------------------------

@router.callback_query(ServiceCallback.filter(), StateFilter(BookingStates.select_service))
async def cb_choose_service(callback: CallbackQuery, callback_data: ServiceCallback, state: FSMContext) -> None:
    service = SERVICES_BY_KEY.get(callback_data.key)
    if service is None:
        await callback.answer()
        return

    if callback_data.key == "other":
        await state.update_data(service_key="other")
        await state.set_state(BookingStates.enter_service_description)
        await callback.message.edit_text(
            "Опишите, пожалуйста, какая работа нужна:", reply_markup=cancel_fsm_kb()
        )
        await callback.answer()
        return

    data = await state.get_data()
    chosen_date = date.fromisoformat(data["date"])
    if not await _slot_still_available(chosen_date, data["time"], service["duration_hours"]):
        await callback.answer()
        await _reject_slot_taken(callback, state, chosen_date)
        return

    await state.update_data(
        service_key=service["key"], service_name=service["name"], duration_hours=service["duration_hours"]
    )
    await state.set_state(BookingStates.enter_name)
    await callback.message.edit_text("👤 Как вас зовут?", reply_markup=cancel_fsm_kb())
    await callback.answer()


@router.message(StateFilter(BookingStates.enter_service_description))
async def process_service_description(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not is_valid_free_text(text, min_len=3, max_len=300):
        await message.answer("Пожалуйста, опишите работу текстом (от 3 до 300 символов).")
        return

    data = await state.get_data()
    chosen_date = date.fromisoformat(data["date"])
    service = SERVICES_BY_KEY["other"]

    if not await _slot_still_available(chosen_date, data["time"], service["duration_hours"]):
        reject_text = "❌ К сожалению, выбранное время уже заняли.\n\nПожалуйста, выберите другое время."
        times = await get_available_start_times(chosen_date, duration_hours=1)
        if times:
            await state.set_state(BookingStates.select_time)
            await message.answer(f"{reject_text}\n\n📅 {format_date_human(chosen_date)}", reply_markup=time_slots_kb(times))
        else:
            await state.set_state(BookingStates.select_date)
            today = date.today()
            view_text, kb = await _calendar_view(today.year, today.month, prefix=reject_text + "\n\n")
            await message.answer(view_text, reply_markup=kb)
        return

    await state.update_data(
        service_key="other", service_name=service["name"], duration_hours=service["duration_hours"],
        service_description=text,
    )
    await state.set_state(BookingStates.enter_name)
    await message.answer("👤 Как вас зовут?", reply_markup=cancel_fsm_kb())


def _final_service_name(data: dict) -> str:
    if data.get("service_key") == "other":
        return f"Другое: {data.get('service_description', '')}"
    return data["service_name"]


# --- Данные клиента -------------------------------------------------------------

@router.message(StateFilter(BookingStates.enter_name))
async def process_name(message: Message, state: FSMContext) -> None:
    if not is_valid_name(message.text or ""):
        await message.answer("Пожалуйста, введите корректное имя (от 2 до 50 символов).")
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(BookingStates.enter_phone)
    await message.answer(
        "📞 Укажите номер телефона.\n\nМожно нажать кнопку ниже или ввести вручную.",
        reply_markup=phone_request_kb(),
    )


async def _save_phone_and_continue(message: Message, state: FSMContext, phone: str) -> None:
    await state.update_data(phone=phone)
    await state.set_state(BookingStates.enter_car_brand)
    await message.answer("Телефон принят ✅", reply_markup=ReplyKeyboardRemove())
    await message.answer("🚗 Укажите марку автомобиля.", reply_markup=cancel_fsm_kb())


@router.message(StateFilter(BookingStates.enter_phone))
async def process_phone(message: Message, state: FSMContext) -> None:
    if message.contact is not None:
        phone_number = message.contact.phone_number
        if not phone_number.startswith("+"):
            phone_number = "+" + phone_number
        await _save_phone_and_continue(message, state, phone_number)
        return

    text = (message.text or "").strip()
    if text == "❌ Отмена":
        await _cancel_fsm_via_message(message, state)
        return
    if not is_valid_phone(text):
        await message.answer("Некорректный номер телефона. Пример: +79991234567")
        return
    await _save_phone_and_continue(message, state, normalize_phone(text))


@router.message(StateFilter(BookingStates.enter_car_brand))
async def process_car_brand(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not is_valid_free_text(text, min_len=1, max_len=50):
        await message.answer("Пожалуйста, укажите марку автомобиля.")
        return
    await state.update_data(car_brand=text)
    await state.set_state(BookingStates.enter_car_model)
    await message.answer("Укажите модель автомобиля.", reply_markup=cancel_fsm_kb())


@router.message(StateFilter(BookingStates.enter_car_model))
async def process_car_model(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not is_valid_free_text(text, min_len=1, max_len=50):
        await message.answer("Пожалуйста, укажите модель автомобиля.")
        return
    await state.update_data(car_model=text)
    await state.set_state(BookingStates.enter_license_plate)
    await message.answer("🔢 Госномер (необязательно):", reply_markup=skip_kb("license_plate"))


LICENSE_PLATE_PROMPT_NEXT = (
    "Есть ли дополнительные комментарии по автомобилю?\n\n"
    "Например:\n«Слышен стук спереди»\n«Нужно подобрать запчасти»\n«Проблема проявляется только на холодную»"
)


@router.message(StateFilter(BookingStates.enter_license_plate))
async def process_license_plate(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not is_valid_free_text(text, min_len=2, max_len=20):
        await message.answer("Госномер выглядит некорректно. Попробуйте ещё раз или нажмите «Пропустить».")
        return
    await state.update_data(license_plate=text)
    await state.set_state(BookingStates.enter_comment)
    await message.answer(LICENSE_PLATE_PROMPT_NEXT, reply_markup=skip_kb("comment"))


@router.callback_query(SkipField.filter(F.field == "license_plate"), StateFilter(BookingStates.enter_license_plate))
async def cb_skip_license_plate(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(license_plate=None)
    await state.set_state(BookingStates.enter_comment)
    await callback.message.edit_text(LICENSE_PLATE_PROMPT_NEXT, reply_markup=skip_kb("comment"))
    await callback.answer()


async def _show_confirmation(state: FSMContext) -> str:
    data = await state.get_data()
    chosen_date = date.fromisoformat(data["date"])
    return format_booking_summary(
        date_str=format_date_human(chosen_date),
        start_time=data["time"],
        name=data["name"],
        phone=data["phone"],
        car_brand=data["car_brand"],
        car_model=data["car_model"],
        license_plate=data.get("license_plate"),
        service_name=_final_service_name(data),
        comment=data.get("comment"),
    )


@router.message(StateFilter(BookingStates.enter_comment))
async def process_comment(message: Message, state: FSMContext) -> None:
    text = (message.text or "").strip()
    if not is_valid_free_text(text, min_len=1, max_len=500):
        await message.answer("Комментарий слишком длинный. Сократите, пожалуйста, или нажмите «Пропустить».")
        return
    await state.update_data(comment=text)
    await state.set_state(BookingStates.confirmation)
    await message.answer(await _show_confirmation(state), reply_markup=confirm_booking_kb())


@router.callback_query(SkipField.filter(F.field == "comment"), StateFilter(BookingStates.enter_comment))
async def cb_skip_comment(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(comment=None)
    await state.set_state(BookingStates.confirmation)
    await callback.message.edit_text(await _show_confirmation(state), reply_markup=confirm_booking_kb())
    await callback.answer()


# --- Подтверждение ---------------------------------------------------------------

@router.callback_query(ConfirmAction.filter(F.action == "cancel"), StateFilter(BookingStates.confirmation))
async def cb_confirm_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "Запись отменена.", reply_markup=main_menu_kb(callback.from_user.id == ADMIN_ID)
    )
    await callback.answer()


@router.callback_query(ConfirmAction.filter(F.action == "edit"), StateFilter(BookingStates.confirmation))
async def cb_confirm_edit(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await _start_booking(callback, state)


@router.callback_query(ConfirmAction.filter(F.action == "confirm"), StateFilter(BookingStates.confirmation))
async def cb_confirm_booking(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    chosen_date = date.fromisoformat(data["date"])
    user = callback.from_user

    try:
        booking = await create_booking(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            target_date=chosen_date,
            start_time=data["time"],
            service_key=data["service_key"],
            service_name=_final_service_name(data),
            duration_hours=data["duration_hours"],
            name=data["name"],
            phone=data["phone"],
            car_brand=data["car_brand"],
            car_model=data["car_model"],
            license_plate=data.get("license_plate"),
            comment=data.get("comment"),
        )
    except BookingError as e:
        if e.code == "slot_taken":
            await callback.answer()
            await _reject_slot_taken(callback, state, chosen_date)
            return
        if e.code == "already_booked":
            await state.clear()
            await callback.message.edit_text(
                "⚠️ У вас уже есть активная запись — сначала отмените её в разделе «Моя запись».",
                reply_markup=back_to_menu_kb(),
            )
            await callback.answer()
            return
        if e.code == "day_closed":
            await state.clear()
            await callback.message.edit_text(
                "К сожалению, этот день закрыт. Пожалуйста, выберите другую дату.",
                reply_markup=back_to_menu_kb(),
            )
            await callback.answer()
            return
        await callback.answer("Не удалось создать запись, попробуйте ещё раз.", show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text(
        f"✅ Запись создана!\n\n📅 {format_date_human(chosen_date)} в {data['time']}\n\n"
        "Ждём вас! Отменить запись можно в разделе «Моя запись».",
        reply_markup=main_menu_kb(user.id == ADMIN_ID),
    )
    await callback.answer()

    await notify_admin_new_booking(callback.bot, booking)
    await notify_channel_new_booking(callback.bot, booking)
    await schedule_reminder(callback.bot, booking.id, booking.date, booking.start_time)
