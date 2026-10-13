"""Постоянное меню, команды и выход из любого шага диалога.

Роутер подключается ПЕРВЫМ: кнопки меню, /start, /menu и /cancel должны срабатывать
в любом состоянии FSM. Иначе, например, нажатие «📋 Моя запись» на шаге ввода имени
записалось бы как имя клиента."""
from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import ADMIN_ID
from handlers.booking import start_booking
from handlers.common import go_home, respond
from handlers.contacts import show_about, show_contacts
from handlers.profile import render_my_booking
from handlers.services import show_services
from keyboards.admin import admin_main_menu_kb
from keyboards.main import BTN_CANCEL, MENU_BUTTON_ACTIONS

router = Router(name="menu")


@router.message(CommandStart())
@router.message(Command("menu"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await go_home(message, state)


@router.message(Command("cancel"))
@router.message(F.text == BTN_CANCEL)
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await go_home(message, state, prefix="Отменено.\n\n")


@router.message(F.text.in_(MENU_BUTTON_ACTIONS))
async def on_menu_button(message: Message, state: FSMContext) -> None:
    action = MENU_BUTTON_ACTIONS[message.text]
    await state.clear()
    if action == "book":
        await start_booking(message, state)
    elif action == "my_booking":
        await render_my_booking(message)
    elif action == "services":
        await show_services(message)
    elif action == "about":
        await show_about(message)
    elif action == "contacts":
        await show_contacts(message)
    elif action == "admin":
        if message.from_user.id == ADMIN_ID:
            await respond(message, "⚙️ <b>Админ-панель</b>", admin_main_menu_kb())
