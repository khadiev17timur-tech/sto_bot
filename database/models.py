"""Модели SQLAlchemy 2.x (async ORM, декларативный стиль с типизацией)."""
from __future__ import annotations

from datetime import date as date_, datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(64))
    first_name: Mapped[Optional[str]] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="user")


class WorkDay(Base):
    """Точечные ИСКЛЮЧЕНИЯ из недельного графика (WORKING_HOURS в config.py).
    Строка создаётся только тогда, когда админ явно закрывает/переоткрывает
    конкретную дату — по умолчанию (без строки) день работает по недельному графику."""
    __tablename__ = "work_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date_] = mapped_column(Date, unique=True, index=True, nullable=False)
    is_working: Mapped[bool] = mapped_column(Boolean, default=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)


class ScheduleSlot(Base):
    """Один часовой интервал расписания на конкретную дату."""
    __tablename__ = "schedule_slots"
    __table_args__ = (UniqueConstraint("date", "start_time", name="uq_slot_date_start"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date_] = mapped_column(Date, index=True, nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)  # "HH:MM"
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    date: Mapped[date_] = mapped_column(Date, index=True, nullable=False)
    start_time: Mapped[str] = mapped_column(String(5), nullable=False)
    end_time: Mapped[str] = mapped_column(String(5), nullable=False)

    status: Mapped[str] = mapped_column(String(16), default="active", index=True)  # active | cancelled

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    car_brand: Mapped[str] = mapped_column(String(64), nullable=False)
    car_model: Mapped[str] = mapped_column(String(64), nullable=False)
    license_plate: Mapped[Optional[str]] = mapped_column(String(20))

    service: Mapped[str] = mapped_column(String(128), nullable=False)
    service_duration: Mapped[int] = mapped_column(Integer, nullable=False)  # в часах
    comment: Mapped[Optional[str]] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="bookings")
    slots: Mapped[list["BookingSlot"]] = relationship(back_populates="booking", cascade="all, delete-orphan")
    reminder: Mapped[Optional["Reminder"]] = relationship(back_populates="booking", cascade="all, delete-orphan")

    __table_args__ = (
        # Гарантия на уровне БД: у одного пользователя не может быть двух активных записей одновременно.
        Index("ux_one_active_booking_per_user", "user_id", unique=True, sqlite_where=text("status = 'active'")),
    )


class BookingSlot(Base):
    """Связка записи с конкретными занятыми слотами (нужна для точного освобождения
    при отмене — особенно для многочасовых услуг, занимающих несколько слотов)."""
    __tablename__ = "booking_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), nullable=False)
    slot_id: Mapped[int] = mapped_column(ForeignKey("schedule_slots.id"), nullable=False)

    booking: Mapped["Booking"] = relationship(back_populates="slots")
    slot: Mapped["ScheduleSlot"] = relationship()


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_id: Mapped[int] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), unique=True, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(nullable=False)
    sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    booking: Mapped["Booking"] = relationship(back_populates="reminder")
