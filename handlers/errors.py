"""Глобальный обработчик ошибок: бот не молчит и не падает, а пишет в лог и возвращает пользователя в меню."""
import logging

from aiogram import Dispatcher
from aiogram.types import ErrorEvent

logger = logging.getLogger(__name__)


async def on_error(event: ErrorEvent) -> bool:
    logger.exception("Необработанная ошибка в хендлере", exc_info=event.exception)
    update = event.update
    try:
        if update.callback_query is not None:
            await update.callback_query.answer("Что-то пошло не так. Попробуйте ещё раз или откройте меню.", show_alert=True)
        elif update.message is not None:
            await update.message.answer("Что-то пошло не так 😔 Попробуйте ещё раз или нажмите /start.")
    except Exception:
        logger.exception("Не удалось сообщить пользователю об ошибке")
    return True


def register(dp: Dispatcher) -> None:
    dp.errors.register(on_error)
