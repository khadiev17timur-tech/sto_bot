"""Точка входа: инициализация БД, планировщика напоминаний и запуск polling."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN
from database.db import init_db
from handlers import register_all_handlers
from database import queries
from services.reminder_service import restore_reminders, scheduler
from services.schedule_service import generate_schedule

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    await init_db()
    logger.info("База данных инициализирована")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    register_all_handlers(dp)

    created_days = await generate_schedule()
    logger.info("Автогенерация расписания: добавлено дней — %s", created_days)

    scheduler.start()
    # Расписание нужно продлевать каждую ночь, иначе через 30 дней непрерывной работы
    # бота новые даты перестанут появляться; прошедшие записи закрываем регулярно.
    scheduler.add_job(generate_schedule, trigger="cron", hour=0, minute=5, id="refresh_schedule", replace_existing=True)
    scheduler.add_job(queries.complete_past_bookings, trigger="interval", minutes=15, id="complete_past", replace_existing=True)
    await queries.complete_past_bookings()
    await restore_reminders(bot)

    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="cancel", description="Отменить текущее действие"),
    ])
    await bot.delete_webhook(drop_pending_updates=True)

    logger.info("Бот запущен")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен")
