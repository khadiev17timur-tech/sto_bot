"""Генерация расписания на основе недельного графика (WORKING_HOURS в config.py)
и поиск доступных времён начала для услуги заданной длительности.

Это единственное место, которое переводит "график работы + длительность услуги"
в конкретные слоты — при изменении WORKING_HOURS в config.py пересчёт произойдёт
автоматически для новых дат."""
from __future__ import annotations

from datetime import date as date_, timedelta

from sqlalchemy import select

from config import MIN_BOOKING_LEAD_MINUTES, SCHEDULE_DAYS_AHEAD, WORKING_HOURS
from database import queries
from utils.timeutil import now as local_now, today as local_today
from database.db import get_session
from database.models import ScheduleSlot


def _to_minutes(time_str: str) -> int:
    h, m = map(int, time_str.split(":"))
    return h * 60 + m


def _to_time_str(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def add_hour(time_str: str) -> str:
    return _to_time_str(_to_minutes(time_str) + 60)


def generate_hourly_times(start: str, end: str) -> list[str]:
    """Часовые интервалы от start до end, не выходящие за end (последний слот
    заканчивается ровно в end или раньше)."""
    start_m, end_m = _to_minutes(start), _to_minutes(end)
    times = []
    cur = start_m
    while cur + 60 <= end_m:
        times.append(_to_time_str(cur))
        cur += 60
    return times


async def generate_slots_for_date(target_date: date_) -> None:
    """Создаёт недостающие слоты на дату по недельному графику. Не трогает уже
    существующие слоты (в т.ч. занятые) и ничего не делает для закрытых дней."""
    if await queries.is_day_closed(target_date):
        return

    weekday = target_date.weekday()
    if weekday not in WORKING_HOURS:
        return

    start, end = WORKING_HOURS[weekday]
    times = generate_hourly_times(start, end)

    async with get_session() as session:
        result = await session.execute(
            select(ScheduleSlot.start_time).where(ScheduleSlot.date == target_date)
        )
        existing_times = set(result.scalars().all())

        for t in times:
            if t in existing_times:
                continue
            session.add(ScheduleSlot(date=target_date, start_time=t, end_time=add_hour(t), is_available=True))

        await session.commit()


async def generate_schedule(days_ahead: int = SCHEDULE_DAYS_AHEAD) -> int:
    """Досоздаёт расписание на days_ahead дней вперёд. Возвращает число новых дней."""
    today = local_today()
    existing_dates = await queries.get_existing_slot_dates()
    created = 0

    for offset in range(days_ahead):
        d = today + timedelta(days=offset)
        if d in existing_dates:
            continue
        if await queries.is_day_closed(d):
            continue
        await generate_slots_for_date(d)
        created += 1

    return created


def is_start_in_past(target_date: date_, start_time: str) -> bool:
    """Слот уже начался или начнётся раньше, чем через MIN_BOOKING_LEAD_MINUTES (время СТО)."""
    now = local_now()
    if target_date != now.date():
        return target_date < now.date()
    return _to_minutes(start_time) < now.hour * 60 + now.minute + MIN_BOOKING_LEAD_MINUTES


async def get_available_start_times(target_date: date_, duration_hours: int) -> list[str]:
    """Времена начала, с которых можно записаться на услугу такой длительности —
    то есть подряд идут duration_hours свободных слотов без разрывов.
    Прошедшее (и слишком близкое) время сегодняшнего дня не предлагается."""
    slots = await queries.get_slots_for_date(target_date)
    if not slots:
        return []

    by_start = {s.start_time: s for s in slots}
    ordered_starts = sorted(by_start.keys(), key=_to_minutes)

    available: list[str] = []
    for t in ordered_starts:
        cur = t
        ok = True
        for _ in range(duration_hours):
            slot = by_start.get(cur)
            if slot is None or not slot.is_available:
                ok = False
                break
            cur = slot.end_time
        if ok:
            available.append(t)

    return [t for t in available if not is_start_in_past(target_date, t)]
