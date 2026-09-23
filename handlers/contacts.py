"""Разделы «О СТО» и «Связаться с нами»."""
from aiogram import F, Router
from aiogram.types import CallbackQuery

from config import STO_ADDRESS, STO_NAME, STO_PHONE, STO_WORKING_HOURS
from keyboards.contacts import contacts_kb
from keyboards.main import MenuAction, back_to_menu_kb

router = Router(name="contacts")


@router.callback_query(MenuAction.filter(F.action == "about"))
async def cb_about(callback: CallbackQuery) -> None:
    lines = [f"📍 <b>{STO_NAME}</b>", ""]
    if STO_ADDRESS:
        lines += ["Адрес:", STO_ADDRESS, ""]
    lines += ["🕐 График:", "", STO_WORKING_HOURS.replace(", ", "\n")]
    if STO_PHONE:
        lines += ["", f"📞 {STO_PHONE}"]
    await callback.message.edit_text("\n".join(lines), reply_markup=back_to_menu_kb())
    await callback.answer()


@router.callback_query(MenuAction.filter(F.action == "contacts"))
async def cb_contacts(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "📞 <b>Связаться с СТО</b>\n\nВыберите удобный способ связи:",
        reply_markup=contacts_kb(),
    )
    await callback.answer()
