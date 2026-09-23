"""Раздел «Моя запись» — просмотр и отмена собственной записи клиентом."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.types import CallbackQuery

from database.models import Booking
from database.queries import get_active_booking_for_telegram_id
from keyboards.booking import MyBookingCancel, my_booking_cancel_confirm_kb, my_booking_kb
from keyboards.main import MenuAction, back_to_menu_kb
from services.booking_service import BookingError, cancel_booking
from services.notification_service import notify_admin_cancelled_booking, notify_channel_cancelled_booking
from services.reminder_service import cancel_reminder
from utils.formatters import format_date_human

logger = logging.getLogger(__name__)

router = Router(name="profile")


def _format_booking_details(booking: Booking) -> str:
    lines = [
        "🗓 <b>Ваша запись:</b>",
        "",
        f"📅 Дата: {format_date_human(booking.date)}",
        f"🕐 Время: {booking.start_time}",
        "",
        f"👤 Имя: {booking.name}",
        f"📞 Телефон: {booking.phone}",
        "",
        f"🚗 Автомобиль: {booking.car_brand} {booking.car_model}",
    ]
    if booking.license_plate:
        lines.append(f"🔢 Госномер: {booking.license_plate}")
    lines.append("")
    lines.append(f"🔧 Услуга: {booking.service}")
    if booking.comment:
        lines.append("")
        lines.append(f"💬 Комментарий:\n{booking.comment}")
    return "\n".join(lines)


async def render_my_booking(callback: CallbackQuery) -> None:
    booking = await get_active_booking_for_telegram_id(callback.from_user.id)
    if booking is None:
        await callback.message.edit_text("У вас пока нет активных записей.", reply_markup=back_to_menu_kb())
        return
    await callback.message.edit_text(_format_booking_details(booking), reply_markup=my_booking_kb())


@router.callback_query(MenuAction.filter(F.action == "my_booking"))
async def cb_my_booking(callback: CallbackQuery) -> None:
    await render_my_booking(callback)
    await callback.answer()


@router.callback_query(MyBookingCancel.filter(F.action == "ask"))
async def cb_cancel_ask(callback: CallbackQuery) -> None:
    booking = await get_active_booking_for_telegram_id(callback.from_user.id)
    if booking is None:
        await callback.answer("У вас нет активной записи.", show_alert=True)
        await render_my_booking(callback)
        return
    await callback.message.edit_text(
        "Вы действительно хотите отменить запись?", reply_markup=my_booking_cancel_confirm_kb()
    )
    await callback.answer()


@router.callback_query(MyBookingCancel.filter(F.action == "no"))
async def cb_cancel_no(callback: CallbackQuery) -> None:
    await render_my_booking(callback)
    await callback.answer("Отмена действия")


@router.callback_query(MyBookingCancel.filter(F.action == "yes"))
async def cb_cancel_yes(callback: CallbackQuery) -> None:
    booking = await get_active_booking_for_telegram_id(callback.from_user.id)
    if booking is None:
        await callback.answer("Запись уже была отменена ранее.", show_alert=True)
        await render_my_booking(callback)
        return

    try:
        cancelled = await cancel_booking(booking_id=booking.id, requesting_telegram_id=callback.from_user.id)
    except BookingError:
        await callback.answer("Не удалось отменить запись — попробуйте ещё раз.", show_alert=True)
        return

    await cancel_reminder(cancelled.id)

    await callback.message.edit_text(
        "✅ Ваша запись отменена.\n\nСлот снова доступен для записи.", reply_markup=back_to_menu_kb()
    )
    await callback.answer()

    await notify_admin_cancelled_booking(callback.bot, cancelled, by_client=True)
    await notify_channel_cancelled_booking(callback.bot, cancelled)
