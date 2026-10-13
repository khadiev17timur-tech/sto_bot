from aiogram import Dispatcher

from handlers import admin, booking, contacts, errors, menu, profile, services, start


def register_all_handlers(dp: Dispatcher) -> None:
    """Порядок важен. Меню — первым: кнопки меню, /start и «Отмена» работают на любом шаге диалога.
    Админ-роутер — следующим: у него на весь роутер стоит фильтр по ADMIN_ID, поэтому обычные
    пользователи проваливаются дальше по цепочке. Запасные обработчики (start) — последними."""
    dp.include_router(menu.router)
    dp.include_router(admin.router)
    dp.include_router(booking.router)
    dp.include_router(profile.router)
    dp.include_router(services.router)
    dp.include_router(contacts.router)
    dp.include_router(start.router)
    errors.register(dp)
