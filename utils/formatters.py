"""Форматирование дат и сообщений для пользователя."""
from __future__ import annotations

from datetime import date as date_
from html import escape as _escape


def esc(value: object) -> str:
    """Текст клиента нельзя вставлять в HTML-сообщение как есть: «<» или «&» ломают разбор Telegram."""
    return _escape(str(value), quote=False)

MONTHS_RU_GENITIVE = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]

WEEKDAYS_RU_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


def format_date_human(d: date_) -> str:
    """25 сентября"""
    return f"{d.day} {MONTHS_RU_GENITIVE[d.month]}"


def format_date_human_with_weekday(d: date_) -> str:
    """25 сентября (Чт)"""
    return f"{format_date_human(d)} ({WEEKDAYS_RU_SHORT[d.weekday()]})"


def format_booking_summary(
    *,
    date_str: str,
    start_time: str,
    name: str,
    phone: str,
    car_brand: str,
    car_model: str,
    license_plate: str | None,
    service_name: str,
    comment: str | None,
) -> str:
    lines = [
        "📋 <b>Проверьте данные записи</b>",
        "",
        f"📅 Дата: {date_str}",
        f"🕐 Время: {start_time}",
        "",
        f"👤 Клиент: {esc(name)}",
        f"📞 Телефон: {esc(phone)}",
        "",
        f"🚗 Автомобиль: {esc(car_brand)} {esc(car_model)}",
    ]
    if license_plate:
        lines.append(f"🔢 Госномер: {esc(license_plate)}")
    lines.append("")
    lines.append(f"🔧 Работа: {esc(service_name)}")
    if comment:
        lines.append("")
        lines.append(f"💬 Комментарий:\n{esc(comment)}")
    return "\n".join(lines)
