"""Клавиатуры админ-панели."""
from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from database.models import Booking, ScheduleSlot
from keyboards.main import MenuAction


class AdminAction(CallbackData, prefix="adm"):
    action: str


class AdminSlotPick(CallbackData, prefix="admslot"):
    slot_id: int


class AdminBookingPick(CallbackData, prefix="admbook"):
    booking_id: int


class AdminYesNo(CallbackData, prefix="admyn"):
    action: str  # yes | no


# Режимы календаря, требующие выбор даты в админке
SCHEDULE_DATE_MODES = {
    "view_schedule", "close_day", "reopen_day",
    "add_working_day", "remove_working_day",
    "add_slot", "remove_slot", "cancel_booking",
}


def admin_main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Расписание", callback_data=AdminAction(action="schedule_menu").pack())],
        [InlineKeyboardButton(text="📋 Записи", callback_data=AdminAction(action="bookings_menu").pack())],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data=MenuAction(action="back").pack())],
    ])


def admin_schedule_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="📋 Расписание на дату", callback_data=AdminAction(action="view_schedule").pack())],
        [InlineKeyboardButton(text="🔒 Закрыть день", callback_data=AdminAction(action="close_day").pack())],
        [InlineKeyboardButton(text="🔓 Открыть день", callback_data=AdminAction(action="reopen_day").pack())],
        [InlineKeyboardButton(text="➕ Добавить рабочий день", callback_data=AdminAction(action="add_working_day").pack())],
        [InlineKeyboardButton(text="➖ Удалить рабочий день", callback_data=AdminAction(action="remove_working_day").pack())],
        [InlineKeyboardButton(text="➕ Добавить слот", callback_data=AdminAction(action="add_slot").pack())],
        [InlineKeyboardButton(text="🗑 Удалить слот", callback_data=AdminAction(action="remove_slot").pack())],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminAction(action="back").pack())],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_bookings_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Записи на дату", callback_data=AdminAction(action="cancel_booking").pack())],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=AdminAction(action="back").pack())],
    ])


def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В админ-панель", callback_data=AdminAction(action="back").pack())]
    ])


def admin_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да", callback_data=AdminYesNo(action="yes").pack()),
            InlineKeyboardButton(text="❌ Нет", callback_data=AdminYesNo(action="no").pack()),
        ]
    ])


def admin_slots_list_kb(slots: list[ScheduleSlot]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{s.start_time}–{s.end_time}", callback_data=AdminSlotPick(slot_id=s.id).pack())]
        for s in slots
    ]
    rows.append([InlineKeyboardButton(text="⬅️ В админ-панель", callback_data=AdminAction(action="back").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_bookings_list_kb(bookings: list[Booking]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=f"{b.start_time} — {b.name} ({b.car_brand} {b.car_model})",
            callback_data=AdminBookingPick(booking_id=b.id).pack(),
        )]
        for b in bookings
    ]
    rows.append([InlineKeyboardButton(text="⬅️ В админ-панель", callback_data=AdminAction(action="back").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)
