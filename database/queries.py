"""Запросы к базе данных, не требующие особой транзакционной атомарности
(чтение, создание пользователя и т.п.). Каждая функция открывает свою сессию.

Критичная к гонкам логика бронирования/отмены живёт в services/booking_service.py —
там нужен явный контроль над одной транзакцией, поэтому она не переиспользует
эти хелперы напрямую."""
from __future__ import annotations

from datetime import date as date_

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from database.db import get_session
from database.models import Booking, BookingSlot, Reminder, ScheduleSlot, User, WorkDay


# ---------------------------------------------------------------------------
# Пользователи
# ---------------------------------------------------------------------------

async def get_or_create_user(telegram_id: int, username: str | None, first_name: str | None) -> User:
    async with get_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is not None:
            # Обновим имя/username, если они поменялись в Telegram
            changed = False
            if user.username != username:
                user.username = username
                changed = True
            if user.first_name != first_name:
                user.first_name = first_name
                changed = True
            if changed:
                await session.commit()
            return user

        user = User(telegram_id=telegram_id, username=username, first_name=first_name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


# ---------------------------------------------------------------------------
# Рабочие дни (исключения из недельного графика)
# ---------------------------------------------------------------------------

async def get_workday_override(target_date: date_) -> WorkDay | None:
    async with get_session() as session:
        result = await session.execute(select(WorkDay).where(WorkDay.date == target_date))
        return result.scalar_one_or_none()


async def is_day_closed(target_date: date_) -> bool:
    override = await get_workday_override(target_date)
    return override is not None and (override.is_closed or not override.is_working)


async def close_day(target_date: date_) -> None:
    async with get_session() as session:
        result = await session.execute(select(WorkDay).where(WorkDay.date == target_date))
        override = result.scalar_one_or_none()
        if override is None:
            session.add(WorkDay(date=target_date, is_working=True, is_closed=True))
        else:
            override.is_closed = True
            override.is_working = True
        await session.commit()


async def reopen_day(target_date: date_) -> None:
    """Убирает исключение для даты — день снова живёт по стандартному недельному графику."""
    async with get_session() as session:
        result = await session.execute(select(WorkDay).where(WorkDay.date == target_date))
        override = result.scalar_one_or_none()
        if override is not None:
            await session.delete(override)
            await session.commit()


async def get_closed_dates(start: date_, end: date_) -> set[date_]:
    async with get_session() as session:
        result = await session.execute(
            select(WorkDay.date).where(
                WorkDay.date.between(start, end),
                (WorkDay.is_closed == True) | (WorkDay.is_working == False),  # noqa: E712
            )
        )
        return set(result.scalars().all())


# ---------------------------------------------------------------------------
# Слоты расписания
# ---------------------------------------------------------------------------

async def get_slots_for_date(target_date: date_) -> list[ScheduleSlot]:
    async with get_session() as session:
        result = await session.execute(
            select(ScheduleSlot).where(ScheduleSlot.date == target_date).order_by(ScheduleSlot.start_time)
        )
        return list(result.scalars().all())


async def has_slots_for_date(target_date: date_) -> bool:
    async with get_session() as session:
        result = await session.execute(
            select(ScheduleSlot.id).where(ScheduleSlot.date == target_date).limit(1)
        )
        return result.scalar_one_or_none() is not None


async def add_slot(target_date: date_, start_time: str, end_time: str) -> None:
    async with get_session() as session:
        exists = await session.execute(
            select(ScheduleSlot).where(ScheduleSlot.date == target_date, ScheduleSlot.start_time == start_time)
        )
        if exists.scalar_one_or_none() is not None:
            return
        session.add(ScheduleSlot(date=target_date, start_time=start_time, end_time=end_time, is_available=True))
        await session.commit()


async def remove_slot(slot_id: int) -> bool:
    """Удаляет свободный слот. Если слот занят записью — не удаляет."""
    async with get_session() as session:
        slot = await session.get(ScheduleSlot, slot_id)
        if slot is None or not slot.is_available:
            return False
        await session.delete(slot)
        await session.commit()
        return True


async def get_existing_slot_dates() -> set[date_]:
    async with get_session() as session:
        result = await session.execute(select(ScheduleSlot.date).distinct())
        return set(result.scalars().all())


async def get_dates_with_available_slots(start: date_, end: date_) -> set[date_]:
    async with get_session() as session:
        result = await session.execute(
            select(ScheduleSlot.date)
            .where(ScheduleSlot.date.between(start, end), ScheduleSlot.is_available == True)  # noqa: E712
            .distinct()
        )
        return set(result.scalars().all())


# ---------------------------------------------------------------------------
# Записи
# ---------------------------------------------------------------------------

async def get_active_booking_for_telegram_id(telegram_id: int) -> Booking | None:
    async with get_session() as session:
        result = await session.execute(
            select(Booking)
            .options(selectinload(Booking.user))
            .join(User)
            .where(User.telegram_id == telegram_id, Booking.status == "active")
        )
        return result.scalar_one_or_none()


async def get_booking(booking_id: int) -> Booking | None:
    """Запись с заранее подгруженным user — чтобы booking.user.telegram_id можно было
    читать и после закрытия сессии (нужно для напоминаний и уведомлений)."""
    async with get_session() as session:
        result = await session.execute(
            select(Booking).options(selectinload(Booking.user)).where(Booking.id == booking_id)
        )
        return result.scalar_one_or_none()


async def get_bookings_for_date(target_date: date_, status: str = "active") -> list[Booking]:
    async with get_session() as session:
        result = await session.execute(
            select(Booking)
            .where(Booking.date == target_date, Booking.status == status)
            .order_by(Booking.start_time)
        )
        return list(result.scalars().all())


async def get_active_future_bookings() -> list[Booking]:
    async with get_session() as session:
        result = await session.execute(select(Booking).where(Booking.status == "active"))
        return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Напоминания
# ---------------------------------------------------------------------------

async def add_reminder(booking_id: int, scheduled_at) -> None:
    async with get_session() as session:
        session.add(Reminder(booking_id=booking_id, scheduled_at=scheduled_at, sent=False))
        await session.commit()


async def delete_reminder(booking_id: int) -> None:
    async with get_session() as session:
        await session.execute(delete(Reminder).where(Reminder.booking_id == booking_id))
        await session.commit()


async def mark_reminder_sent(booking_id: int) -> None:
    async with get_session() as session:
        result = await session.execute(select(Reminder).where(Reminder.booking_id == booking_id))
        reminder = result.scalar_one_or_none()
        if reminder is not None:
            reminder.sent = True
            await session.commit()


async def get_pending_reminders() -> list[Reminder]:
    """Активные (несработавшие) напоминания для активных записей — используется при старте бота."""
    async with get_session() as session:
        result = await session.execute(
            select(Reminder).join(Booking).where(Reminder.sent == False, Booking.status == "active")  # noqa: E712
        )
        return list(result.scalars().all())
