"""Inline-календарь. Общий для клиентской записи и админ-панели — поведение
регулируется параметром mode, который прокидывается в callback_data, а дальше
конкретный handler решает, что делать с выбранной датой."""
from __future__ import annotations

import calendar
from datetime import date

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

MONTH_NAMES_RU = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]
WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


class CalendarNav(CallbackData, prefix="calnav"):
    mode: str
    year: int
    month: int


class CalendarDay(CallbackData, prefix="calday"):
    mode: str
    date: str  # YYYY-MM-DD


class CalendarIgnore(CallbackData, prefix="calign"):
    pass


def build_calendar(
    year: int,
    month: int,
    mode: str,
    min_date: date,
    max_date: date,
    highlighted_dates: set[str] | None = None,
    closed_dates: set[str] | None = None,
    only_highlighted_clickable: bool = True,
    back_button: InlineKeyboardButton | None = None,
) -> InlineKeyboardMarkup:
    """Строит календарь на месяц (year, month).

    highlighted_dates — даты, которые нужно отметить как доступные (есть свободные слоты).
    only_highlighted_clickable — True: кликабельны только даты из highlighted_dates
        (пользовательская запись). False: кликабельны все даты в диапазоне
        [min_date, max_date], кроме закрытых (админ-панель).
    """
    highlighted_dates = highlighted_dates or set()
    closed_dates = closed_dates or set()

    rows: list[list[InlineKeyboardButton]] = []

    rows.append([
        InlineKeyboardButton(text=f"{MONTH_NAMES_RU[month]} {year}", callback_data=CalendarIgnore().pack())
    ])
    rows.append([
        InlineKeyboardButton(text=wd, callback_data=CalendarIgnore().pack()) for wd in WEEKDAYS_RU
    ])

    cal = calendar.Calendar(firstweekday=0)
    week_row: list[InlineKeyboardButton] = []
    for day in cal.itermonthdates(year, month):
        if day.month != month:
            week_row.append(InlineKeyboardButton(text=" ", callback_data=CalendarIgnore().pack()))
        else:
            iso = day.isoformat()
            in_range = min_date <= day <= max_date
            is_closed = iso in closed_dates
            is_highlighted = iso in highlighted_dates

            if only_highlighted_clickable:
                clickable = in_range and is_highlighted and not is_closed
            else:
                clickable = in_range and not is_closed

            if not in_range:
                text = f"·{day.day}·"
            elif is_closed:
                text = f"🔒{day.day}"
            elif is_highlighted:
                text = f"✅{day.day}" if only_highlighted_clickable else str(day.day)
            else:
                text = "—" if only_highlighted_clickable and in_range else str(day.day)

            cb = CalendarDay(mode=mode, date=iso).pack() if clickable else CalendarIgnore().pack()
            week_row.append(InlineKeyboardButton(text=text, callback_data=cb))

        if len(week_row) == 7:
            rows.append(week_row)
            week_row = []

    nav_row: list[InlineKeyboardButton] = []

    prev_month_anchor = date(year - 1, 12, 1) if month == 1 else date(year, month - 1, 1)
    if prev_month_anchor >= date(min_date.year, min_date.month, 1):
        py, pm = (year - 1, 12) if month == 1 else (year, month - 1)
        nav_row.append(InlineKeyboardButton(
            text="⬅️", callback_data=CalendarNav(mode=mode, year=py, month=pm).pack()
        ))
    else:
        nav_row.append(InlineKeyboardButton(text=" ", callback_data=CalendarIgnore().pack()))

    next_month_anchor = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    if next_month_anchor <= max_date:
        ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
        nav_row.append(InlineKeyboardButton(
            text="➡️", callback_data=CalendarNav(mode=mode, year=ny, month=nm).pack()
        ))
    else:
        nav_row.append(InlineKeyboardButton(text=" ", callback_data=CalendarIgnore().pack()))

    rows.append(nav_row)
    if back_button is not None:
        rows.append([back_button])

    return InlineKeyboardMarkup(inline_keyboard=rows)
