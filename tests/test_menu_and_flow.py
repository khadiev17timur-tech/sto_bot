"""Постоянное меню, выход из диалога, полный сценарий записи и защита от записи в прошлое."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from tests.conftest import ADMIN, CLIENT
from database import queries
from keyboards.calendar import CalendarDay
from keyboards.main import BTN_ABOUT, BTN_ADMIN, BTN_BOOK, BTN_CANCEL, BTN_CONTACTS, BTN_MY_BOOKING, BTN_SERVICES
from services import schedule_service
from services.booking_service import BookingError, create_booking
from utils.timeutil import today


# ---------- постоянное меню ----------

async def test_start_shows_persistent_menu(h):
    await h.send(CLIENT, "/start")
    assert "Тест-СТО" in h.last_text(CLIENT)
    kb = h.last(CLIENT).markup
    assert kb.is_persistent and kb.resize_keyboard
    assert h.reply_kb_texts(CLIENT) == [BTN_BOOK, BTN_MY_BOOKING, BTN_SERVICES, BTN_ABOUT, BTN_CONTACTS]


async def test_admin_button_only_for_admin(h):
    await h.send(ADMIN, "/start")
    assert BTN_ADMIN in h.reply_kb_texts(ADMIN)
    await h.send(CLIENT, "/start")
    assert BTN_ADMIN not in h.reply_kb_texts(CLIENT)


async def test_client_cannot_open_admin_panel_by_text(h):
    await h.send(CLIENT, BTN_ADMIN)
    assert "Админ-панель" not in h.all_text(CLIENT)


async def test_admin_button_opens_panel(h):
    await h.send(ADMIN, BTN_ADMIN)
    assert "Админ-панель" in h.last_text(ADMIN)


@pytest.mark.parametrize("button,expected", [
    (BTN_SERVICES, "УСЛУГИ И ЦЕНЫ"),
    (BTN_ABOUT, "Тест-СТО"),
    (BTN_CONTACTS, "Связаться"),
    (BTN_MY_BOOKING, "нет активных записей"),
])
async def test_menu_buttons_work_by_text(h, button, expected):
    await h.send(CLIENT, button)
    assert expected in h.last_text(CLIENT)


async def test_book_button_opens_calendar(h):
    await h.send(CLIENT, BTN_BOOK)
    assert "Выберите дату" in h.last_text(CLIENT)


# ---------- выход из диалога ----------

async def test_menu_button_in_middle_of_booking_is_not_saved_as_name(h):
    await h.send(CLIENT, BTN_BOOK)
    await _pick_date_time_service(h, CLIENT)
    assert "Как вас зовут" in h.last_text(CLIENT)
    await h.send(CLIENT, BTN_SERVICES)           # раньше это записалось бы как имя
    assert "УСЛУГИ И ЦЕНЫ" in h.last_text(CLIENT)
    await h.send(CLIENT, "Иван")                 # диалог сброшен — имя больше не ждут
    assert "Не совсем понял" in h.last_text(CLIENT)


async def test_start_command_in_middle_of_booking_resets_it(h):
    await h.send(CLIENT, BTN_BOOK)
    await _pick_date_time_service(h, CLIENT)
    await h.send(CLIENT, "/start")
    assert "Добро пожаловать" in h.last_text(CLIENT)
    await h.send(CLIENT, "Иван")
    assert "Не совсем понял" in h.last_text(CLIENT)


async def test_unknown_command_is_not_accepted_as_name(h):
    await h.send(CLIENT, BTN_BOOK)
    await _pick_date_time_service(h, CLIENT)
    await h.send(CLIENT, "/foo")
    assert "корректное имя" in h.last_text(CLIENT)


async def test_phone_step_has_cancel_and_it_works(h):
    await _book_until_phone(h, CLIENT)
    kb = h.last(CLIENT).markup
    labels = [b.text for row in kb.keyboard for b in row]
    assert BTN_CANCEL in labels and any(b.request_contact for row in kb.keyboard for b in row)
    await h.send(CLIENT, BTN_CANCEL)
    assert "Отменено" in h.last_text(CLIENT)
    assert h.reply_kb_texts(CLIENT)[0] == BTN_BOOK


async def test_cancel_command_works(h):
    await h.send(CLIENT, BTN_BOOK)
    await h.send(CLIENT, "/cancel")
    assert "Отменено" in h.last_text(CLIENT)


async def test_garbage_message_gets_hint_with_menu(h):
    await h.send(CLIENT, "абракадабра")
    assert "кнопками меню" in h.last_text(CLIENT)
    assert BTN_BOOK in h.reply_kb_texts(CLIENT)


async def test_stale_inline_button_goes_home(h):
    await h.send(CLIENT, "/start")
    out = h.last(CLIENT)
    await h.press(CLIENT, out, "totally:unknown")
    assert "Добро пожаловать" in h.last_text(CLIENT)


# ---------- полный сценарий ----------

async def test_full_booking_flow_keeps_menu_and_notifies_admin(h):
    await _book_until_phone(h, CLIENT)
    await h.send_contact(CLIENT, "79991234567")
    assert "Телефон принят" in h.all_text(CLIENT)
    assert h.reply_kb_texts(CLIENT)[0] == BTN_BOOK          # постоянное меню вернулось после запроса номера
    await h.send(CLIENT, "Toyota")
    await h.send(CLIENT, "Camry")
    await h.click(CLIENT, "Пропустить")
    await h.click(CLIENT, "Пропустить")
    assert "Проверьте данные" in h.last_text(CLIENT)
    await h.click(CLIENT, "Подтвердить")
    assert "Запись создана" in h.last_text(CLIENT)
    booking = await queries.get_active_booking_for_telegram_id(CLIENT)
    assert booking is not None and booking.phone == "+79991234567" and booking.car_brand == "Toyota"
    assert "НОВАЯ ЗАПИСЬ" in h.last_text(ADMIN)


async def test_my_booking_via_button_and_cancel(h):
    await _book_until_phone(h, CLIENT)
    await h.send(CLIENT, "+7 999 123-45-67")
    await h.send(CLIENT, "Lada")
    await h.send(CLIENT, "Vesta")
    await h.click(CLIENT, "Пропустить")
    await h.click(CLIENT, "Пропустить")
    await h.click(CLIENT, "Подтвердить")
    await h.send(CLIENT, BTN_MY_BOOKING)
    assert "Ваша запись" in h.last_text(CLIENT) and "Lada Vesta" in h.last_text(CLIENT)
    await h.click(CLIENT, "Отменить запись")
    await h.click(CLIENT, "Да, отменить")
    assert "отменена" in h.last_text(CLIENT)
    assert await queries.get_active_booking_for_telegram_id(CLIENT) is None
    assert "ЗАПИСЬ ОТМЕНЕНА" in h.last_text(ADMIN)


async def test_second_booking_blocked_via_button(h):
    await _book_until_phone(h, CLIENT)
    await h.send(CLIENT, "+79991234567")
    await h.send(CLIENT, "Lada")
    await h.send(CLIENT, "Vesta")
    await h.click(CLIENT, "Пропустить")
    await h.click(CLIENT, "Пропустить")
    await h.click(CLIENT, "Подтвердить")
    await h.send(CLIENT, BTN_BOOK)
    assert "уже есть активная запись" in h.last_text(CLIENT)


# ---------- прошедшее время ----------

class _FrozenNow:
    def __init__(self, dt: datetime):
        self.dt = dt

    def __call__(self):
        return self.dt


async def test_past_slots_today_are_not_offered(h, monkeypatch):
    now = datetime.combine(today(), datetime.min.time()).replace(hour=15, minute=30)
    monkeypatch.setattr(schedule_service, "local_now", _FrozenNow(now))
    if not await queries.get_slots_for_date(today()):
        pytest.skip("на сегодня нет слотов")
    times = await schedule_service.get_available_start_times(today(), 1)
    assert times and min(times) >= "16:30"      # 15:30 + 60 минут запаса; слоты часовые, значит с 17:00
    assert "09:00" not in times and "15:00" not in times


async def test_cannot_book_past_slot_even_by_force(h, monkeypatch):
    now = datetime.combine(today(), datetime.min.time()).replace(hour=15, minute=30)
    monkeypatch.setattr(schedule_service, "local_now", _FrozenNow(now))
    with pytest.raises(BookingError) as e:
        await create_booking(
            telegram_id=CLIENT, username="u", first_name="И", target_date=today(), start_time="09:00",
            service_key="oil_change", service_name="Замена масла", duration_hours=1, name="Иван",
            phone="+79991234567", car_brand="A", car_model="B", license_plate=None, comment=None,
        )
    assert e.value.code == "slot_taken"


async def test_future_days_are_fully_available(h):
    tomorrow = today() + timedelta(days=1)
    times = await schedule_service.get_available_start_times(tomorrow, 1)
    assert "09:00" in times


async def test_today_not_highlighted_when_only_past_slots_left(h, monkeypatch):
    now = datetime.combine(today(), datetime.min.time()).replace(hour=23, minute=0)
    monkeypatch.setattr(schedule_service, "local_now", _FrozenNow(now))
    await h.send(CLIENT, BTN_BOOK)
    days = [CalendarDay.unpack(b.callback_data).date for b in h.inline_buttons(h.last(CLIENT))
            if b.callback_data and b.callback_data.startswith("calday")]
    assert today().isoformat() not in days


# ---------- часовой пояс ----------

def test_timeutil_uses_sto_timezone():
    from zoneinfo import ZoneInfo
    from utils.timeutil import now
    expected = datetime.now(ZoneInfo("Europe/Moscow")).replace(tzinfo=None)
    assert abs((now() - expected).total_seconds()) < 5


# ---------- помощники ----------

async def _pick_date_time_service(h, uid):
    """Из календаря: ближайшая будущая дата → 09:00 (первое время) → «Замена масла»."""
    out = h.last(uid)
    tomorrow = (today() + timedelta(days=1)).isoformat()
    days = [b for b in h.inline_buttons(out) if b.callback_data and b.callback_data.startswith("calday")]
    pick = next((b for b in days if CalendarDay.unpack(b.callback_data).date == tomorrow), None)
    if pick is None:   # завтра уже следующий месяц — листаем
        await h.click_data(uid, "calnav", not_contains="")
        days = [b for b in h.inline_buttons(h.last(uid)) if b.callback_data and b.callback_data.startswith("calday")]
        pick = next(b for b in days if CalendarDay.unpack(b.callback_data).date == tomorrow)
    await h.press(uid, h.last(uid), pick.callback_data)
    await h.click_data(uid, "time")
    await h.click(uid, "Замена масла")


async def _book_until_phone(h, uid):
    await h.send(uid, BTN_BOOK)
    await _pick_date_time_service(h, uid)
    await h.send(uid, "Иван")
    assert "номер телефона" in h.last_text(uid)


async def test_reminder_is_scheduled_in_sto_timezone(h, monkeypatch):
    """Сервер в UTC, СТО в Москве: напоминание считается от московского «сейчас», а не от часов сервера."""
    from services import reminder_service
    monkeypatch.setattr(reminder_service, "local_now", _FrozenNow(datetime(2030, 1, 1, 8, 0)))

    async def _noop(*a, **kw):
        return None
    monkeypatch.setattr(reminder_service.queries, "add_reminder", _noop)
    await reminder_service.schedule_reminder(h.bot, 987654, date(2030, 1, 2), "10:00")
    job = reminder_service.scheduler.get_job("reminder_987654")
    assert job is not None
    assert job.trigger.run_date.replace(tzinfo=None) == datetime(2030, 1, 1, 10, 0)
    assert str(job.trigger.run_date.tzinfo) == "Europe/Moscow"
    # визит ровно через 24 часа или раньше — напоминать уже поздно
    await reminder_service.schedule_reminder(h.bot, 987655, date(2030, 1, 2), "08:00")
    assert reminder_service.scheduler.get_job("reminder_987655") is None
