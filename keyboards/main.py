"""Главное меню."""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class MenuAction(CallbackData, prefix="menu"):
    action: str  # book | my_booking | services | about | contacts | admin | back


def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="🚗 Записаться на СТО", callback_data=MenuAction(action="book").pack())],
        [InlineKeyboardButton(text="📋 Моя запись", callback_data=MenuAction(action="my_booking").pack())],
        [InlineKeyboardButton(text="🔧 Услуги и цены", callback_data=MenuAction(action="services").pack())],
        [InlineKeyboardButton(text="📍 О СТО", callback_data=MenuAction(action="about").pack())],
        [InlineKeyboardButton(text="📞 Связаться с нами", callback_data=MenuAction(action="contacts").pack())],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(text="⚙️ Админ-панель", callback_data=MenuAction(action="admin").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В меню", callback_data=MenuAction(action="back").pack())]
    ])
