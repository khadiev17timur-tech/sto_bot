"""Создание и отмена записей. Это единственное место, где выполняется атомарная
проверка+захват слотов — все остальные части бота обязаны идти через эти функции,
а не трогать ScheduleSlot/Booking напрямую."""
from __future__ import annotations

import logging
from datetime import date as date_

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from database.db import get_session
from database.models import Booking, BookingSlot, ScheduleSlot, User
from database.queries import get_or_create_user, is_day_closed
from services.schedule_service import add_hour

logger = logging.getLogger(__name__)


class BookingError(Exception):
    """code: already_booked | day_closed | slot_taken | not_found | already_cancelled | not_owner"""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


async def create_booking(
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    target_date: date_,
    start_time: str,
    service_key: str,
    service_name: str,
    duration_hours: int,
    name: str,
    phone: str,
    car_brand: str,
    car_model: str,
    license_plate: str | None,
    comment: str | None,
) -> Booking:
    """Атомарно проверяет доступность нужных слотов и создаёт запись.

    Никогда не полагается только на предварительную проверку (которая делалась
    раньше в диалоге) — здесь всё перепроверяется заново внутри одной транзакции,
    а захват слотов выполняется условным UPDATE ... WHERE is_available = 1, что
    защищает от двух пользователей, одновременно бронирующих один и тот же слот
    (SQLite сериализует конкурентные писателей на уровне файла, см. database/db.py).
    """
    if await is_day_closed(target_date):
        raise BookingError("day_closed")

    user = await get_or_create_user(telegram_id, username, first_name)

    required_times = []
    cur = start_time
    for _ in range(duration_hours):
        required_times.append(cur)
        cur = add_hour(cur)

    async with get_session() as session:
        try:
            existing = await session.execute(
                select(Booking.id).where(Booking.user_id == user.id, Booking.status == "active")
            )
            if existing.scalar_one_or_none() is not None:
                raise BookingError("already_booked")

            result = await session.execute(
                select(ScheduleSlot).where(
                    ScheduleSlot.date == target_date,
                    ScheduleSlot.start_time.in_(required_times),
                )
            )
            slots = {s.start_time: s for s in result.scalars().all()}
            if len(slots) != duration_hours or any(not slots[t].is_available for t in required_times):
                raise BookingError("slot_taken")

            slot_ids = [slots[t].id for t in required_times]

            upd = await session.execute(
                update(ScheduleSlot)
                .where(ScheduleSlot.id.in_(slot_ids), ScheduleSlot.is_available == True)  # noqa: E712
                .values(is_available=False)
            )
            if upd.rowcount != duration_hours:
                # Кто-то успел захватить хотя бы один из слотов между SELECT и UPDATE.
                raise BookingError("slot_taken")

            booking = Booking(
                user_id=user.id,
                date=target_date,
                start_time=start_time,
                end_time=slots[required_times[-1]].end_time,
                status="active",
                name=name,
                phone=phone,
                car_brand=car_brand,
                car_model=car_model,
                license_plate=license_plate or None,
                service=service_name,
                service_duration=duration_hours,
                comment=comment or None,
            )
            session.add(booking)
            await session.flush()

            for slot_id in slot_ids:
                session.add(BookingSlot(booking_id=booking.id, slot_id=slot_id))

            await session.commit()
        except BookingError:
            await session.rollback()
            raise
        except IntegrityError:
            await session.rollback()
            logger.warning("IntegrityError при создании записи user_id=%s", user.id)
            raise BookingError("already_booked")

        await session.refresh(booking)
        booking.user = user
        return booking


async def cancel_booking(*, booking_id: int, requesting_telegram_id: int | None) -> Booking:
    """requesting_telegram_id=None означает отмену администратором (право уже
    проверено выше по стеку через ADMIN_ID). Иначе — сверяем, что запись
    действительно принадлежит этому telegram_id, не доверяя ничему из callback_data."""
    async with get_session() as session:
        result = await session.execute(
            select(Booking).options(selectinload(Booking.slots), selectinload(Booking.user)).where(Booking.id == booking_id)
        )
        booking = result.scalar_one_or_none()
        if booking is None:
            raise BookingError("not_found")
        if booking.status != "active":
            raise BookingError("already_cancelled")
        if requesting_telegram_id is not None and booking.user.telegram_id != requesting_telegram_id:
            raise BookingError("not_owner")

        booking.status = "cancelled"
        slot_ids = [bs.slot_id for bs in booking.slots]
        if slot_ids:
            await session.execute(
                update(ScheduleSlot).where(ScheduleSlot.id.in_(slot_ids)).values(is_available=True)
            )
        await session.commit()
        await session.refresh(booking)
        return booking
