"""/start, главное меню, общий обработчик "пустых" ячеек календаря."""
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import ADMIN_ID, STO_NAME
from keyboards.calendar import CalendarIgnore
from keyboards.main import MenuAction, main_menu_kb

router = Router(name="start")


def welcome_text() -> str:
    return (
        f"🚗 <b>Добро пожаловать в {STO_NAME}!</b>\n\n"
        "Здесь вы можете:\n\n"
        "• записаться на обслуживание;\n"
        "• посмотреть услуги и цены;\n"
        "• посмотреть свою запись;\n"
        "• связаться с нами.\n\n"
        "Выберите нужный раздел ниже."
    )


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    is_admin = message.from_user.id == ADMIN_ID
    await message.answer(welcome_text(), reply_markup=main_menu_kb(is_admin=is_admin))


@router.callback_query(MenuAction.filter(F.action == "back"))
async def cb_back_to_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    is_admin = callback.from_user.id == ADMIN_ID
    try:
        await callback.message.edit_text(welcome_text(), reply_markup=main_menu_kb(is_admin=is_admin))
    except Exception:
        # На случай, если предыдущее сообщение нельзя отредактировать (например, было с reply-клавиатурой)
        await callback.message.answer(welcome_text(), reply_markup=main_menu_kb(is_admin=is_admin))
    await callback.answer()


@router.callback_query(CalendarIgnore.filter())
async def cb_calendar_ignore(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query()
async def cb_stale_button(callback: CallbackQuery, state: FSMContext) -> None:
    """Запасной обработчик: кнопка устарела (например, после перезапуска бота)."""
    await state.clear()
    await callback.answer("Эта кнопка устарела, открываю меню 🙂")
    is_admin = callback.from_user.id == ADMIN_ID
    await callback.message.answer(welcome_text(), reply_markup=main_menu_kb(is_admin=is_admin))
