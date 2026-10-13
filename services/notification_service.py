"""Уведомления администратору и в Telegram-канал/чат расписания.
Канал используется ТОЛЬКО для информирования — никакой обязательной подписки."""
from __future__ import annotations

import logging

from aiogram import Bot

from config import ADMIN_ID, SCHEDULE_CHANNEL_ID
from database.models import Booking
from utils.formatters import esc, format_date_human

logger = logging.getLogger(__name__)


def _booking_block(booking: Booking) -> str:
    lines = [
        f"{format_date_human(booking.date)} | {booking.start_time}",
        "",
        f"👤 {esc(booking.name)}",
        f"📞 {esc(booking.phone)}",
        "",
        f"🚗 {esc(booking.car_brand)} {esc(booking.car_model)}",
    ]
    if booking.license_plate:
        lines.append(f"🔢 {esc(booking.license_plate)}")
    lines.append("")
    lines.append(f"🔧 {esc(booking.service)}")
    if booking.comment:
        lines.append("")
        lines.append(f"💬 {esc(booking.comment)}")
    return "\n".join(lines)


async def notify_admin_new_booking(bot: Bot, booking: Booking) -> None:
    text = "🆕 <b>НОВАЯ ЗАПИСЬ</b>\n\n" + _booking_block(booking)
    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception:
        logger.exception("Не удалось уведомить администратора о новой записи #%s", booking.id)


async def notify_admin_cancelled_booking(bot: Bot, booking: Booking, by_client: bool) -> None:
    who = "клиент" if by_client else "администратор"
    text = f"❌ <b>ЗАПИСЬ ОТМЕНЕНА</b> (отменил: {who})\n\n" + _booking_block(booking)
    try:
        await bot.send_message(ADMIN_ID, text)
    except Exception:
        logger.exception("Не удалось уведомить администратора об отмене записи #%s", booking.id)


async def notify_channel_new_booking(bot: Bot, booking: Booking) -> None:
    if not SCHEDULE_CHANNEL_ID:
        return
    text = "📅 <b>НОВАЯ ЗАПИСЬ</b>\n\n" + _booking_block(booking)
    try:
        await bot.send_message(SCHEDULE_CHANNEL_ID, text)
    except Exception:
        logger.exception(
            "Не удалось отправить запись в канал расписания (booking #%s). "
            "Проверьте, что бот добавлен в чат и имеет права на отправку сообщений.",
            booking.id,
        )


async def notify_channel_cancelled_booking(bot: Bot, booking: Booking) -> None:
    if not SCHEDULE_CHANNEL_ID:
        return
    text = (
        "❌ <b>ЗАПИСЬ ОТМЕНЕНА</b>\n\n"
        f"{format_date_human(booking.date)} | {booking.start_time}\n\n"
        f"👤 {esc(booking.name)}\n"
        f"🚗 {esc(booking.car_brand)} {esc(booking.car_model)}\n\n"
        f"🔧 {esc(booking.service)}\n\n"
        "Слот снова свободен."
    )
    try:
        await bot.send_message(SCHEDULE_CHANNEL_ID, text)
    except Exception:
        logger.exception("Не удалось отправить отмену в канал расписания (booking #%s)", booking.id)


async def notify_client_cancelled_by_admin(bot: Bot, booking: Booking) -> None:
    text = (
        "⚠️ Ваша запись на СТО была отменена администратором.\n\n"
        f"📅 {format_date_human(booking.date)} в {booking.start_time}\n\n"
        "Если это недоразумение — свяжитесь с нами через «📞 Связаться с нами» в главном меню."
    )
    try:
        await bot.send_message(booking.user.telegram_id, text)
    except Exception:
        logger.exception("Не удалось уведомить клиента об отмене записи администратором #%s", booking.id)
