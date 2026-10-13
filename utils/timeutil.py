"""Текущее время в часовом поясе СТО (config.TIMEZONE).

Сервер хостинга живёт в UTC, а график работы и напоминания заданы по местному времени СТО.
Везде, где нужно «сейчас» или «сегодня», берём эти функции, а не date.today()/datetime.now().
Возвращаем «наивные» datetime: время в поясе СТО без tzinfo — так они хранятся в БД."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from config import TIMEZONE

TZ = ZoneInfo(TIMEZONE)


def now() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None)


def today() -> date:
    return now().date()
