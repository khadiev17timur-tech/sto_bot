"""Клавиатура «Связаться с нами». Кнопки WhatsApp/Telegram появляются, только
если соответствующие ссылки заданы в .env — так реализовано "отключение через
конфигурацию" без правки логики бота."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import STO_PHONE, TELEGRAM_URL, WHATSAPP_URL
from keyboards.main import MenuAction


def contacts_kb() -> InlineKeyboardMarkup:
    rows = []
    if STO_PHONE:
        rows.append([InlineKeyboardButton(text="📞 Позвонить", url=f"tel:{STO_PHONE}")])
    if WHATSAPP_URL:
        rows.append([InlineKeyboardButton(text="💬 WhatsApp", url=WHATSAPP_URL)])
    if TELEGRAM_URL:
        rows.append([InlineKeyboardButton(text="✈️ Telegram", url=TELEGRAM_URL)])
    rows.append([InlineKeyboardButton(text="⬅️ В меню", callback_data=MenuAction(action="back").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)
