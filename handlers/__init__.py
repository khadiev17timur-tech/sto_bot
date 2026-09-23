from aiogram import Dispatcher

from handlers import admin, booking, contacts, profile, services, start


def register_all_handlers(dp: Dispatcher) -> None:
    """Админ-роутер регистрируем первым: у него на весь роутер стоит фильтр по
    ADMIN_ID, поэтому обычные пользователи всё равно провалятся дальше по цепочке."""
    dp.include_router(admin.router)
    dp.include_router(booking.router)
    dp.include_router(profile.router)
    dp.include_router(services.router)
    dp.include_router(contacts.router)
    dp.include_router(start.router)
