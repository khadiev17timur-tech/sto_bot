"""Раздел «Услуги и цены»."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from config import PRICE_LIST_TEXT
from handlers.common import respond
from keyboards.main import MenuAction, back_to_menu_kb

router = Router(name="services")


async def show_services(event: Message | CallbackQuery) -> None:
    await respond(event, PRICE_LIST_TEXT, back_to_menu_kb())


@router.callback_query(MenuAction.filter(F.action == "services"))
async def cb_services(callback: CallbackQuery) -> None:
    await show_services(callback)
    await callback.answer()
