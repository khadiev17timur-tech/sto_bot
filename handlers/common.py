"""Общие помощники для хендлеров: ответ на сообщение или на нажатие inline-кнопки одним вызовом."""
from __future__ import annotations

import logging

from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from config import ADMIN_ID
from keyboards.main import main_reply_kb

logger = logging.getLogger(__name__)


def user_id_of(event: Message | CallbackQuery) -> int:
    return event.from_user.id


async def respond(event: Message | CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """Нажатие inline-кнопки → правим то же сообщение; кнопка постоянного меню/команда → новое сообщение."""
    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=reply_markup)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                return
            # Сообщение нельзя отредактировать (старое/удалено) — отправляем новое.
            await event.message.answer(text, reply_markup=reply_markup)
    else:
        await event.answer(text, reply_markup=reply_markup)


async def go_home(event: Message | CallbackQuery, state: FSMContext, prefix: str = "") -> None:
    """Сбрасывает диалог и показывает приветствие вместе с постоянным меню."""
    from handlers.start import welcome_text  # локально: start.py тоже импортирует common

    await state.clear()
    message = event.message if isinstance(event, CallbackQuery) else event
    if isinstance(event, CallbackQuery):
        try:
            await event.message.delete()
        except TelegramBadRequest:
            pass
    await message.answer(prefix + welcome_text(), reply_markup=main_reply_kb(event.from_user.id == ADMIN_ID))
