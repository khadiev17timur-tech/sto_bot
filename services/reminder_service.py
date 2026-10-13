"""Напоминания клиентам за REMINDER_HOURS_BEFORE часов до визита (APScheduler)."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import REMINDER_HOURS_BEFORE
from utils.timeutil import TZ, now as local_now
from database import queries
from utils.formatters import format_date_human

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=TZ)


def _job_id(booking_id: int) -> str:
    return f"reminder_{booking_id}"


def _booking_datetime(date_, time_str: str) -> datetime:
    h, m = map(int, time_str.split(":"))
    return datetime(date_.year, date_.month, date_.day, h, m)


async def _send_reminder(bot: Bot, booking_id: int) -> None:
    booking = await queries.get_booking(booking_id)
    if booking is None or booking.status != "active":
        await queries.delete_reminder(booking_id)
        return

    text = (
        "🔔 <b>Напоминание о записи</b>\n\n"
        "Завтра вы записаны на СТО:\n\n"
        f"📅 {format_date_human(booking.date)}\n"
        f"🕐 {booking.start_time}\n\n"
        f"🚗 {booking.car_brand} {booking.car_model}\n"
        f"🔧 {booking.service}\n\n"
        "Ждём вас!"
    )
    try:
        await bot.send_message(booking.user.telegram_id, text)
        logger.info("Напоминание отправлено по записи #%s", booking_id)
    except Exception:
        logger.exception("Не удалось отправить напоминание по записи #%s", booking_id)
    await queries.mark_reminder_sent(booking_id)
    await queries.delete_reminder(booking_id)


async def schedule_reminder(bot: Bot, booking_id: int, date_, start_time: str) -> None:
    """Планирует напоминание. Если до визита осталось меньше REMINDER_HOURS_BEFORE
    часов — напоминание намеренно не создаётся (по требованиям ТЗ)."""
    appointment_dt = _booking_datetime(date_, start_time)
    remind_at = appointment_dt - timedelta(hours=REMINDER_HOURS_BEFORE)

    if remind_at <= local_now():
        return

    job_id = _job_id(booking_id)
    scheduler.add_job(
        _send_reminder,
        trigger="date",
        run_date=remind_at,
        args=[bot, booking_id],
        id=job_id,
        replace_existing=True,
    )
    await queries.add_reminder(booking_id, remind_at)
    logger.info("Напоминание по записи #%s запланировано на %s", booking_id, remind_at)


async def cancel_reminder(booking_id: int) -> None:
    job_id = _job_id(booking_id)
    job = scheduler.get_job(job_id)
    if job is not None:
        job.remove()
    await queries.delete_reminder(booking_id)


async def restore_reminders(bot: Bot) -> None:
    """Восстанавливает задачи APScheduler из БД после перезапуска бота, не создавая дублей."""
    pending = await queries.get_pending_reminders()
    now = local_now()
    restored = 0

    for reminder in pending:
        booking = await queries.get_booking(reminder.booking_id)
        if booking is None or booking.status != "active":
            await queries.delete_reminder(reminder.booking_id)
            continue

        appointment_dt = _booking_datetime(booking.date, booking.start_time)
        if appointment_dt <= now:
            # Визит уже прошёл, пока бот был выключен.
            await queries.delete_reminder(reminder.booking_id)
            continue

        run_date = reminder.scheduled_at if reminder.scheduled_at > now else now + timedelta(seconds=5)
        scheduler.add_job(
            _send_reminder,
            trigger="date",
            run_date=run_date,
            args=[bot, reminder.booking_id],
            id=_job_id(reminder.booking_id),
            replace_existing=True,
        )
        restored += 1

    logger.info("Восстановлено напоминаний после перезапуска: %s", restored)
