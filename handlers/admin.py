"""Админ-панель. Доступна только пользователю с ADMIN_ID (фильтр на весь router —
никакой user_id из callback_data здесь никогда не используется для авторизации)."""
from __future__ import annotations

from datetime import date, timedelta

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ADMIN_ID
from database import queries
from keyboards.admin import (
    SCHEDULE_DATE_MODES,
    AdminAction,
    AdminBookingPick,
    AdminSlotPick,
    AdminYesNo,
    admin_back_kb,
    admin_bookings_list_kb,
    admin_bookings_menu_kb,
    admin_confirm_kb,
    admin_main_menu_kb,
    admin_schedule_menu_kb,
    admin_slots_list_kb,
)
from keyboards.calendar import CalendarDay, CalendarNav, build_calendar
from keyboards.main import MenuAction
from services.booking_service import BookingError, cancel_booking
from services.notification_service import (
    notify_admin_cancelled_booking,
    notify_channel_cancelled_booking,
    notify_client_cancelled_by_admin,
)
from services.reminder_service import cancel_reminder
from services.schedule_service import add_hour, generate_slots_for_date
from states.admin import AdminStates
from utils.formatters import format_date_human
from utils.validators import is_valid_time

router = Router(name="admin")
router.message.filter(F.from_user.id == ADMIN_ID)
router.callback_query.filter(F.from_user.id == ADMIN_ID)

ADMIN_DAYS_AHEAD = 90

MODE_TITLES = {
    "view_schedule": "📅 Выберите дату для просмотра расписания:",
    "close_day": "📅 Выберите дату, которую нужно закрыть:",
    "reopen_day": "📅 Выберите дату, которую нужно вновь открыть (отмечены закрытые дни):",
    "add_working_day": "📅 Выберите дату — на неё будут сформированы стандартные рабочие слоты:",
    "remove_working_day": "📅 Выберите дату, которую нужно исключить из рабочего графика:",
    "add_slot": "📅 Выберите дату, на которую нужно добавить слот:",
    "remove_slot": "📅 Выберите дату, на которой нужно удалить слот (отмечены дни со свободными слотами):",
    "cancel_booking": "📅 Выберите дату, чтобы отменить запись клиента:",
}


def _admin_date_range() -> tuple[date, date]:
    today = date.today()
    return today, today + timedelta(days=ADMIN_DAYS_AHEAD)


async def _calendar_kwargs(mode: str) -> dict:
    """Для каждого режима — своё правило, какие даты кликабельны и как отмечены.
    Например, для reopen_day кликабельны ТОЛЬКО закрытые даты (обратная логика)."""
    if mode in ("view_schedule", "cancel_booking"):
        dates = await queries.get_existing_slot_dates()
        return dict(highlighted_dates={d.isoformat() for d in dates}, closed_dates=set(), only_highlighted_clickable=True)

    if mode == "remove_slot":
        min_date, max_date = _admin_date_range()
        dates = await queries.get_dates_with_available_slots(min_date, max_date)
        return dict(highlighted_dates={d.isoformat() for d in dates}, closed_dates=set(), only_highlighted_clickable=True)

    if mode == "reopen_day":
        min_date, max_date = _admin_date_range()
        closed = await queries.get_closed_dates(min_date, max_date)
        return dict(highlighted_dates={d.isoformat() for d in closed}, closed_dates=set(), only_highlighted_clickable=True)

    if mode in ("close_day", "remove_working_day"):
        min_date, max_date = _admin_date_range()
        closed = {d.isoformat() for d in await queries.get_closed_dates(min_date, max_date)}
        return dict(highlighted_dates=set(), closed_dates=closed, only_highlighted_clickable=False)

    # add_working_day, add_slot — любая дата в диапазоне, включая уже закрытые
    return dict(highlighted_dates=set(), closed_dates=set(), only_highlighted_clickable=False)


async def _render_admin_calendar(callback: CallbackQuery, year: int, month: int, mode: str) -> None:
    min_date, max_date = _admin_date_range()
    kwargs = await _calendar_kwargs(mode)
    kb = build_calendar(year, month, mode=mode, min_date=min_date, max_date=max_date, **kwargs)
    await callback.message.edit_text(MODE_TITLES[mode], reply_markup=kb)


# --- Меню админки --------------------------------------------------------------

@router.callback_query(MenuAction.filter(F.action == "admin"))
async def cb_admin_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("⚙️ <b>Админ-панель</b>", reply_markup=admin_main_menu_kb())
    await callback.answer()


@router.callback_query(AdminAction.filter(F.action == "back"))
async def cb_admin_back(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("⚙️ <b>Админ-панель</b>", reply_markup=admin_main_menu_kb())
    await callback.answer()


@router.callback_query(AdminAction.filter(F.action == "schedule_menu"))
async def cb_schedule_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("📅 <b>Расписание</b>", reply_markup=admin_schedule_menu_kb())
    await callback.answer()


@router.callback_query(AdminAction.filter(F.action == "bookings_menu"))
async def cb_bookings_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("📋 <b>Записи</b>", reply_markup=admin_bookings_menu_kb())
    await callback.answer()


@router.callback_query(AdminAction.filter(F.action.in_(SCHEDULE_DATE_MODES)))
async def cb_admin_pick_mode(callback: CallbackQuery, callback_data: AdminAction, state: FSMContext) -> None:
    mode = callback_data.action
    await state.set_state(AdminStates.choose_date)
    await state.update_data(admin_mode=mode)
    today = date.today()
    await _render_admin_calendar(callback, today.year, today.month, mode)
    await callback.answer()


@router.callback_query(CalendarNav.filter(F.mode.in_(SCHEDULE_DATE_MODES)))
async def cb_admin_calendar_nav(callback: CallbackQuery, callback_data: CalendarNav) -> None:
    await _render_admin_calendar(callback, callback_data.year, callback_data.month, callback_data.mode)
    await callback.answer()


# --- Выбор даты в зависимости от режима -----------------------------------------

@router.callback_query(CalendarDay.filter(F.mode.in_(SCHEDULE_DATE_MODES)))
async def cb_admin_calendar_day(callback: CallbackQuery, callback_data: CalendarDay, state: FSMContext) -> None:
    mode = callback_data.mode
    chosen_date = date.fromisoformat(callback_data.date)
    await state.update_data(date=callback_data.date)

    if mode == "view_schedule":
        await state.clear()
        await _show_schedule(callback, chosen_date)

    elif mode == "close_day":
        bookings = await queries.get_bookings_for_date(chosen_date, status="active")
        note = (
            f"\n\n⚠️ На эту дату {len(bookings)} активных записей — они НЕ будут отменены автоматически."
            if bookings else ""
        )
        await state.set_state(AdminStates.close_day_confirm)
        await callback.message.edit_text(
            f"Закрыть день {format_date_human(chosen_date)}? Клиенты больше не смогут записаться на эту дату.{note}",
            reply_markup=admin_confirm_kb(),
        )

    elif mode == "reopen_day":
        await state.set_state(AdminStates.reopen_day_confirm)
        await callback.message.edit_text(
            f"Снова открыть день {format_date_human(chosen_date)} для записи?", reply_markup=admin_confirm_kb()
        )

    elif mode == "add_working_day":
        await state.set_state(AdminStates.add_working_day_confirm)
        await callback.message.edit_text(
            f"Сформировать стандартное расписание на {format_date_human(chosen_date)}?",
            reply_markup=admin_confirm_kb(),
        )

    elif mode == "remove_working_day":
        bookings = await queries.get_bookings_for_date(chosen_date, status="active")
        note = (
            f"\n\n⚠️ На эту дату {len(bookings)} активных записей — они НЕ будут отменены автоматически."
            if bookings else ""
        )
        await state.set_state(AdminStates.remove_working_day_confirm)
        await callback.message.edit_text(
            f"Исключить {format_date_human(chosen_date)} из рабочего графика?{note}",
            reply_markup=admin_confirm_kb(),
        )

    elif mode == "add_slot":
        await state.set_state(AdminStates.add_slot_enter_time)
        await callback.message.edit_text(
            f"Введите время слота для {format_date_human(chosen_date)} в формате ЧЧ:ММ (например, 12:00):",
            reply_markup=admin_back_kb(),
        )

    elif mode == "remove_slot":
        slots = await queries.get_slots_for_date(chosen_date)
        available = [s for s in slots if s.is_available]
        if not available:
            await callback.answer("На эту дату нет свободных слотов для удаления.", show_alert=True)
            return
        await state.set_state(AdminStates.remove_slot_pick)
        await callback.message.edit_text(
            f"Слоты на {format_date_human(chosen_date)}. Выберите, какой удалить:",
            reply_markup=admin_slots_list_kb(available),
        )

    elif mode == "cancel_booking":
        bookings = await queries.get_bookings_for_date(chosen_date, status="active")
        if not bookings:
            await callback.answer("На эту дату нет активных записей.", show_alert=True)
            return
        await state.set_state(AdminStates.cancel_booking_pick)
        await callback.message.edit_text(
            f"Записи на {format_date_human(chosen_date)}. Выберите, какую отменить:",
            reply_markup=admin_bookings_list_kb(bookings),
        )

    await callback.answer()


async def _show_schedule(callback: CallbackQuery, chosen_date: date) -> None:
    slots = await queries.get_slots_for_date(chosen_date)
    is_closed = await queries.is_day_closed(chosen_date)
    bookings = await queries.get_bookings_for_date(chosen_date, status="active")

    header = f"📅 <b>Расписание на {format_date_human(chosen_date)}</b>" + (" 🔒 (день закрыт)" if is_closed else "")

    if not slots:
        await callback.message.edit_text(header + "\n\nРасписание на этот день не сформировано.", reply_markup=admin_back_kb())
        return

    # Разворачиваем многочасовые записи в карту "занятое время -> запись", чтобы
    # корректно подписать и стартовый слот, и слоты-продолжения.
    occupied: dict[str, object] = {}
    for b in bookings:
        cur = b.start_time
        for _ in range(b.service_duration):
            occupied[cur] = b
            cur = add_hour(cur)

    lines = [header, ""]
    for slot in slots:
        if slot.is_available:
            lines.append(f"🟢 {slot.start_time} Свободно")
            continue
        booking = occupied.get(slot.start_time)
        if booking is None:
            lines.append(f"⚫️ {slot.start_time} Недоступно")
        elif booking.start_time == slot.start_time:
            lines.append(f"🔴 {slot.start_time} — {booking.name} — {booking.car_brand} {booking.car_model} ({booking.service})")
        else:
            lines.append(f"🔴 {slot.start_time} — (продолжение записи: {booking.name})")

    await callback.message.edit_text("\n".join(lines), reply_markup=admin_back_kb())


# --- Подтверждения для close/reopen/add/remove working day ---------------------

@router.callback_query(AdminYesNo.filter(), StateFilter(AdminStates.close_day_confirm))
async def cb_close_day_confirm(callback: CallbackQuery, callback_data: AdminYesNo, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    if callback_data.action == "yes":
        chosen_date = date.fromisoformat(data["date"])
        await queries.close_day(chosen_date)
        await callback.message.edit_text(f"🔒 День {format_date_human(chosen_date)} закрыт.", reply_markup=admin_back_kb())
    else:
        await callback.message.edit_text("Действие отменено.", reply_markup=admin_main_menu_kb())
    await callback.answer()


@router.callback_query(AdminYesNo.filter(), StateFilter(AdminStates.reopen_day_confirm))
async def cb_reopen_day_confirm(callback: CallbackQuery, callback_data: AdminYesNo, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    if callback_data.action == "yes":
        chosen_date = date.fromisoformat(data["date"])
        await queries.reopen_day(chosen_date)
        await generate_slots_for_date(chosen_date)
        await callback.message.edit_text(f"🔓 День {format_date_human(chosen_date)} снова открыт.", reply_markup=admin_back_kb())
    else:
        await callback.message.edit_text("Действие отменено.", reply_markup=admin_main_menu_kb())
    await callback.answer()


@router.callback_query(AdminYesNo.filter(), StateFilter(AdminStates.add_working_day_confirm))
async def cb_add_working_day_confirm(callback: CallbackQuery, callback_data: AdminYesNo, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    if callback_data.action == "yes":
        chosen_date = date.fromisoformat(data["date"])
        await queries.reopen_day(chosen_date)
        await generate_slots_for_date(chosen_date)
        await callback.message.edit_text(f"✅ Рабочий день {format_date_human(chosen_date)} добавлен.", reply_markup=admin_back_kb())
    else:
        await callback.message.edit_text("Действие отменено.", reply_markup=admin_main_menu_kb())
    await callback.answer()


@router.callback_query(AdminYesNo.filter(), StateFilter(AdminStates.remove_working_day_confirm))
async def cb_remove_working_day_confirm(callback: CallbackQuery, callback_data: AdminYesNo, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    if callback_data.action == "yes":
        chosen_date = date.fromisoformat(data["date"])
        await queries.close_day(chosen_date)
        await callback.message.edit_text(
            f"➖ День {format_date_human(chosen_date)} исключён из рабочего графика.", reply_markup=admin_back_kb()
        )
    else:
        await callback.message.edit_text("Действие отменено.", reply_markup=admin_main_menu_kb())
    await callback.answer()


# --- Добавление слота: ввод времени ---------------------------------------------

@router.message(StateFilter(AdminStates.add_slot_enter_time))
async def process_add_slot_time(message: Message, state: FSMContext) -> None:
    time_str = (message.text or "").strip()
    if not is_valid_time(time_str):
        await message.answer("Некорректный формат времени. Введите в формате ЧЧ:ММ, например 14:00")
        return

    data = await state.get_data()
    chosen_date = date.fromisoformat(data["date"])
    if await queries.is_day_closed(chosen_date):
        await message.answer("Этот день закрыт. Сначала откройте его через «Открыть день» или «Добавить рабочий день».")
        await state.clear()
        return

    await queries.add_slot(chosen_date, time_str, add_hour(time_str))
    await state.clear()
    await message.answer(f"✅ Слот {format_date_human(chosen_date)} {time_str} добавлен.", reply_markup=admin_back_kb())


# --- Удаление слота ---------------------------------------------------------------

@router.callback_query(AdminSlotPick.filter(), StateFilter(AdminStates.remove_slot_pick))
async def cb_remove_slot(callback: CallbackQuery, callback_data: AdminSlotPick, state: FSMContext) -> None:
    removed = await queries.remove_slot(callback_data.slot_id)
    await state.clear()
    if removed:
        await callback.message.edit_text("🗑 Слот удалён.", reply_markup=admin_back_kb())
    else:
        await callback.message.edit_text(
            "Не удалось удалить: слот уже занят записью. Сначала отмените запись клиента.",
            reply_markup=admin_back_kb(),
        )
    await callback.answer()


# --- Отмена записи клиента ---------------------------------------------------------

@router.callback_query(AdminBookingPick.filter(), StateFilter(AdminStates.cancel_booking_pick))
async def cb_admin_pick_booking(callback: CallbackQuery, callback_data: AdminBookingPick, state: FSMContext) -> None:
    booking = await queries.get_booking(callback_data.booking_id)
    if booking is None or booking.status != "active":
        await callback.answer("Эта запись уже отменена.", show_alert=True)
        return
    await state.update_data(booking_id=callback_data.booking_id)
    await state.set_state(AdminStates.cancel_booking_confirm)
    await callback.message.edit_text(
        f"Отменить запись <b>{booking.name}</b> на {format_date_human(booking.date)} в {booking.start_time}?",
        reply_markup=admin_confirm_kb(),
    )
    await callback.answer()


@router.callback_query(AdminYesNo.filter(), StateFilter(AdminStates.cancel_booking_confirm))
async def cb_admin_cancel_booking_confirm(callback: CallbackQuery, callback_data: AdminYesNo, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    if callback_data.action != "yes":
        await callback.message.edit_text("Действие отменено.", reply_markup=admin_main_menu_kb())
        await callback.answer()
        return

    try:
        booking = await cancel_booking(booking_id=data["booking_id"], requesting_telegram_id=None)
    except BookingError:
        await callback.message.edit_text("Не удалось отменить — возможно, запись уже была отменена.", reply_markup=admin_back_kb())
        await callback.answer()
        return

    await cancel_reminder(booking.id)
    await callback.message.edit_text("✅ Запись клиента отменена.", reply_markup=admin_back_kb())
    await callback.answer()

    await notify_admin_cancelled_booking(callback.bot, booking, by_client=False)
    await notify_channel_cancelled_booking(callback.bot, booking)
    await notify_client_cancelled_by_admin(callback.bot, booking)
