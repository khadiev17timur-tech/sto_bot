"""Главное меню: постоянная клавиатура внизу чата (reply keyboard) и inline-кнопка «В меню»."""
from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


class MenuAction(CallbackData, prefix="menu"):
    action: str  # book | my_booking | services | about | contacts | admin | back


# Тексты кнопок постоянного меню. По ним же handlers/menu.py ловит нажатия.
BTN_BOOK = "🚗 Записаться на СТО"
BTN_MY_BOOKING = "📋 Моя запись"
BTN_SERVICES = "🔧 Услуги и цены"
BTN_ABOUT = "📍 О СТО"
BTN_CONTACTS = "📞 Связаться с нами"
BTN_ADMIN = "⚙️ Админ-панель"
BTN_CANCEL = "❌ Отмена"

MENU_BUTTON_ACTIONS = {
    BTN_BOOK: "book",
    BTN_MY_BOOKING: "my_booking",
    BTN_SERVICES: "services",
    BTN_ABOUT: "about",
    BTN_CONTACTS: "contacts",
    BTN_ADMIN: "admin",
}


def main_reply_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Постоянное меню: не пропадает после нажатия, работает в любой момент диалога."""
    rows = [
        [KeyboardButton(text=BTN_BOOK)],
        [KeyboardButton(text=BTN_MY_BOOKING), KeyboardButton(text=BTN_SERVICES)],
        [KeyboardButton(text=BTN_ABOUT), KeyboardButton(text=BTN_CONTACTS)],
    ]
    if is_admin:
        rows.append([KeyboardButton(text=BTN_ADMIN)])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выберите действие в меню ниже",
    )


def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ В меню", callback_data=MenuAction(action="back").pack())]
    ])
