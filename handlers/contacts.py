"""Разделы «О СТО» и «Связаться с нами»."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from config import STO_ADDRESS, STO_NAME, STO_PHONE, STO_WORKING_HOURS
from handlers.common import respond
from keyboards.contacts import contacts_kb
from keyboards.main import MenuAction, back_to_menu_kb

router = Router(name="contacts")


async def show_about(event: Message | CallbackQuery) -> None:
    lines = [f"📍 <b>{STO_NAME}</b>", ""]
    if STO_ADDRESS:
        lines += ["Адрес:", STO_ADDRESS, ""]
    lines += ["🕐 График:", "", STO_WORKING_HOURS.replace(", ", "\n")]
    if STO_PHONE:
        lines += ["", f"📞 {STO_PHONE}"]
    await respond(event, "\n".join(lines), back_to_menu_kb())


@router.callback_query(MenuAction.filter(F.action == "about"))
async def cb_about(callback: CallbackQuery) -> None:
    await show_about(callback)
    await callback.answer()


async def show_contacts(event: Message | CallbackQuery) -> None:
    text = "📞 <b>Связаться с СТО</b>\n\n"
    if STO_PHONE:
        text += f"Телефон: {STO_PHONE}\n(нажмите на номер, чтобы позвонить)\n\n"
    text += "Или выберите удобный способ связи:"
    await respond(event, text, contacts_kb())


@router.callback_query(MenuAction.filter(F.action == "contacts"))
async def cb_contacts(callback: CallbackQuery) -> None:
    await show_contacts(callback)
    await callback.answer()
