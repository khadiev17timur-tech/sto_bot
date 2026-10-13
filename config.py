"""Конфигурация бота. Секреты и данные конкретного СТО берутся из .env —
логика бота их не знает и не зависит от них напрямую."""
import os

from dotenv import load_dotenv

load_dotenv()

# --- Основные параметры ---
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
_admin_raw = os.getenv("ADMIN_ID", "").strip()
if _admin_raw and not _admin_raw.lstrip("-").isdigit():
    raise RuntimeError(f"ADMIN_ID должен быть числом (Telegram ID из @userinfobot), а не {_admin_raw!r}")
ADMIN_ID: int = int(_admin_raw or "0")
SCHEDULE_CHANNEL_ID: str = os.getenv("SCHEDULE_CHANNEL_ID", "")

DB_PATH: str = os.getenv("DB_PATH", "data/sto_bot.db")

# Часовой пояс СТО. Хостинг (Bothost) работает в UTC, поэтому «сегодня», «сейчас» и
# напоминания считаем явно в поясе СТО, а не по часам сервера.
TIMEZONE: str = os.getenv("TIMEZONE", "Europe/Moscow")
# За сколько минут до начала ещё можно записаться на сегодняшний слот
MIN_BOOKING_LEAD_MINUTES: int = int(os.getenv("MIN_BOOKING_LEAD_MINUTES", "60"))

if not BOT_TOKEN:
    raise RuntimeError("Не задан BOT_TOKEN (в .env или в переменных окружения хостинга)")
if not ADMIN_ID:
    raise RuntimeError("Не задан ADMIN_ID (в .env или в переменных окружения хостинга)")

# --- Информация о СТО ---
STO_NAME: str = os.getenv("STO_NAME", "Автосервис TORQUE")
STO_ADDRESS: str = os.getenv("STO_ADDRESS", "")
STO_PHONE: str = os.getenv("STO_PHONE", "")
STO_WORKING_HOURS: str = os.getenv(
    "STO_WORKING_HOURS", "ПН-ПТ 09:00-19:00, СБ 09:00-18:00, ВС 09:00-17:00"
)
WHATSAPP_URL: str = os.getenv("WHATSAPP_URL", "")
TELEGRAM_URL: str = os.getenv("TELEGRAM_URL", "")

# --- График работы СТО ---
# Ключ — день недели (0 = понедельник ... 6 = воскресенье), значение — (открытие, закрытие).
# Единственное место, где меняется рабочий график — слоты пересчитываются от этого словаря.
WORKING_HOURS: dict[int, tuple[str, str]] = {
    0: ("09:00", "19:00"),
    1: ("09:00", "19:00"),
    2: ("09:00", "19:00"),
    3: ("09:00", "19:00"),
    4: ("09:00", "19:00"),
    5: ("09:00", "18:00"),
    6: ("09:00", "17:00"),
}

# Длительность одного слота в расписании (в часах). Услуги длиннее одного слота
# занимают несколько последовательных слотов подряд (см. SERVICES ниже).
SLOT_DURATION_HOURS: int = 1

# На сколько дней вперёд автоматически формируется расписание
SCHEDULE_DAYS_AHEAD: int = 30

# За сколько часов до визита присылать напоминание
REMINDER_HOURS_BEFORE: int = 24

# --- Услуги и ориентировочные цены (Москва) ---
# Единственное место, где меняются услуги, их длительность и цена.
# price_from = None означает "цена по договорённости" (актуально для "Другое").
# Длительность указана в часах и определяет, сколько последовательных часовых
# слотов будет занято при записи на эту услугу.
SERVICES: list[dict] = [
    {"key": "oil_change", "emoji": "🛢", "name": "Замена масла", "duration_hours": 1, "price_from": 1000},
    {"key": "maintenance", "emoji": "🔧", "name": "Техническое обслуживание", "duration_hours": 1, "price_from": 2500},
    {"key": "diagnostics", "emoji": "🔍", "name": "Компьютерная диагностика", "duration_hours": 1, "price_from": 2000},
    {"key": "suspension_diag", "emoji": "⚙️", "name": "Диагностика подвески", "duration_hours": 1, "price_from": 1000},
    {"key": "tire_service", "emoji": "🛞", "name": "Шиномонтаж", "duration_hours": 1, "price_from": 2000},
    {"key": "alignment", "emoji": "📐", "name": "Развал-схождение", "duration_hours": 1, "price_from": 2500},
    {"key": "brakes", "emoji": "🛑", "name": "Тормозная система", "duration_hours": 1, "price_from": 1500},
    {"key": "electrics", "emoji": "🔋", "name": "Электрика / диагностика электрооборудования", "duration_hours": 1, "price_from": 1500},
    {"key": "suspension_repair", "emoji": "🚗", "name": "Ремонт подвески", "duration_hours": 2, "price_from": 3500},
    {"key": "other", "emoji": "⚙️", "name": "Другое", "duration_hours": 1, "price_from": None},
]

SERVICES_BY_KEY: dict[str, dict] = {s["key"]: s for s in SERVICES}

PRICE_DISCLAIMER: str = (
    "\n\nℹ️ Указанные цены являются ориентировочными.\n"
    "Точная стоимость зависит от автомобиля, сложности работ и стоимости запчастей."
)


def build_price_list_html() -> str:
    lines = ["<b>🔧 УСЛУГИ И ЦЕНЫ</b>", "", "<i>Ориентировочная стоимость работ (Москва)</i>", ""]
    for s in SERVICES:
        if s["key"] == "other":
            continue
        price = f"от {s['price_from']:,} ₽".replace(",", " ") if s["price_from"] else "по договорённости"
        lines.append(f"{s['emoji']} <b>{s['name']}</b>\n{price}\n")
    return "\n".join(lines).rstrip() + PRICE_DISCLAIMER


PRICE_LIST_TEXT: str = build_price_list_html()
