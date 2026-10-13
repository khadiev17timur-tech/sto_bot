"""Приветствие, кнопка «В меню», пустые ячейки календаря и запасные обработчики."""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ADMIN_ID, STO_NAME
from handlers.common import go_home
from keyboards.calendar import CalendarIgnore
from keyboards.main import MenuAction, main_reply_kb

router = Router(name="start")


def welcome_text() -> str:
    return (
        f"🚗 <b>Добро пожаловать в {STO_NAME}!</b>\n\n"
        "Здесь вы можете:\n\n"
        "• записаться на обслуживание;\n"
        "• посмотреть услуги и цены;\n"
        "• посмотреть свою запись;\n"
        "• связаться с нами.\n\n"
        "Меню всегда под рукой — кнопки внизу экрана 👇"
    )


@router.callback_query(MenuAction.filter(F.action == "back"))
async def cb_back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await go_home(callback, state)
    await callback.answer()


@router.callback_query(CalendarIgnore.filter())
async def cb_calendar_ignore(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query()
async def cb_stale_button(callback: CallbackQuery, state: FSMContext) -> None:
    """Запасной обработчик: кнопка устарела (например, после перезапуска бота)."""
    await callback.answer("Эта кнопка устарела, открываю меню 🙂")
    await go_home(callback, state)


@router.message()
async def msg_fallback(message: Message) -> None:
    """Любое сообщение, которое не подошло ни под один шаг диалога."""
    await message.answer(
        "Не совсем понял 🤔 Пользуйтесь кнопками меню внизу экрана.",
        reply_markup=main_reply_kb(message.from_user.id == ADMIN_ID),
    )
