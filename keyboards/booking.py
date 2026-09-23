"""Клавиатуры сценария записи клиента."""
from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from config import SERVICES
from keyboards.main import MenuAction


class CancelFSM(CallbackData, prefix="cancelfsm"):
    pass


class ServiceCallback(CallbackData, prefix="svc"):
    key: str


class TimeCallback(CallbackData, prefix="time"):
    time: str


class SkipField(CallbackData, prefix="skip"):
    field: str  # license_plate | comment


class ConfirmAction(CallbackData, prefix="bconf"):
    action: str  # confirm | edit | cancel


class ActiveBookingAction(CallbackData, prefix="activeb"):
    action: str  # view | cancel | back


class MyBookingCancel(CallbackData, prefix="mybc"):
    action: str  # ask | yes | no


def cancel_fsm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data=CancelFSM().pack())]
    ])


def service_list_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"{s['emoji']} {s['name']}", callback_data=ServiceCallback(key=s["key"]).pack())]
        for s in SERVICES
    ]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data=CancelFSM().pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def time_slots_kb(times: list[str]) -> InlineKeyboardMarkup:
    rows = []
    row: list[InlineKeyboardButton] = []
    for t in times:
        row.append(InlineKeyboardButton(text=t, callback_data=TimeCallback(time=t).pack()))
        if len(row) == 4:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data=CancelFSM().pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def phone_request_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Отправить номер телефона", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def remove_reply_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def skip_kb(field: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data=SkipField(field=field).pack())],
        [InlineKeyboardButton(text="❌ Отмена", callback_data=CancelFSM().pack())],
    ])


def confirm_booking_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=ConfirmAction(action="confirm").pack())],
        [
            InlineKeyboardButton(text="✏️ Изменить", callback_data=ConfirmAction(action="edit").pack()),
            InlineKeyboardButton(text="❌ Отмена", callback_data=ConfirmAction(action="cancel").pack()),
        ],
    ])


def active_booking_conflict_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Посмотреть запись", callback_data=ActiveBookingAction(action="view").pack())],
        [InlineKeyboardButton(text="❌ Отменить запись", callback_data=ActiveBookingAction(action="cancel").pack())],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=ActiveBookingAction(action="back").pack())],
    ])


def my_booking_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить запись", callback_data=MyBookingCancel(action="ask").pack())],
        [InlineKeyboardButton(text="⬅️ В меню", callback_data=MenuAction(action="back").pack())],
    ])


def my_booking_cancel_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, отменить", callback_data=MyBookingCancel(action="yes").pack()),
            InlineKeyboardButton(text="↩️ Нет", callback_data=MyBookingCancel(action="no").pack()),
        ]
    ])
