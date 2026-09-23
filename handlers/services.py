"""Раздел «Услуги и цены»."""
from aiogram import F, Router
from aiogram.types import CallbackQuery

from config import PRICE_LIST_TEXT
from keyboards.main import MenuAction, back_to_menu_kb

router = Router(name="services")


@router.callback_query(MenuAction.filter(F.action == "services"))
async def cb_services(callback: CallbackQuery) -> None:
    await callback.message.edit_text(PRICE_LIST_TEXT, reply_markup=back_to_menu_kb())
    await callback.answer()
