"""Тестовый стенд: настоящий Dispatcher + поддельная сессия Telegram (без сети и токена)."""
from __future__ import annotations

import os
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

# Настройки задаём ДО импорта проекта: config.py читает окружение при импорте.
_TMP = tempfile.mkdtemp(prefix="sto_tests_")
os.environ.update(
    BOT_TOKEN="123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    ADMIN_ID="900",
    DB_PATH=str(Path(_TMP) / "test.db"),
    STO_NAME="Тест-СТО",
    TIMEZONE="Asia/Yekaterinburg",
    STO_PHONE="+79990000000",
    SCHEDULE_CHANNEL_ID="",
)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest_asyncio  # noqa: E402
from aiogram import Bot, Dispatcher  # noqa: E402
from aiogram.client.default import DefaultBotProperties  # noqa: E402
from aiogram.client.session.base import BaseSession  # noqa: E402
from aiogram.enums import ParseMode  # noqa: E402
from aiogram.fsm.storage.memory import MemoryStorage  # noqa: E402
from aiogram.methods import DeleteMessage, EditMessageText, SendMessage  # noqa: E402
from aiogram.types import InlineKeyboardMarkup, Message, ReplyKeyboardMarkup, Update  # noqa: E402

from database.db import engine  # noqa: E402
from database.models import Base  # noqa: E402
from handlers import register_all_handlers  # noqa: E402
from services.reminder_service import scheduler  # noqa: E402
from services.schedule_service import generate_schedule  # noqa: E402

ADMIN = 900
CLIENT = 100


@dataclass
class Out:
    chat_id: int
    message_id: int
    text: str | None
    markup: object
    tick: int
    deleted: bool = False


class FakeTelegram(BaseSession):
    def __init__(self):
        super().__init__()
        self.outbox: list[Out] = []
        self._ids = 5000
        self._tick = 0

    async def close(self) -> None:
        pass

    async def stream_content(self, *a, **kw):  # pragma: no cover
        yield b""

    def _msg(self, bot, chat_id, message_id, text):
        return Message.model_validate({
            "message_id": message_id, "date": int(time.time()), "chat": {"id": chat_id, "type": "private"},
            "from": {"id": bot.id, "is_bot": True, "first_name": "bot"}, "text": text,
        }, context={"bot": bot})

    def _find(self, chat_id, message_id):
        return next((o for o in self.outbox if o.chat_id == chat_id and o.message_id == message_id), None)

    async def make_request(self, bot, method, timeout=None):
        self._tick += 1
        if isinstance(method, SendMessage):
            self._ids += 1
            self.outbox.append(Out(method.chat_id, self._ids, method.text, method.reply_markup, self._tick))
            return self._msg(bot, method.chat_id, self._ids, method.text)
        if isinstance(method, EditMessageText):
            out = self._find(method.chat_id, method.message_id)
            if out is not None:
                out.text, out.markup, out.tick = method.text, method.reply_markup, self._tick
            return self._msg(bot, method.chat_id, method.message_id, method.text)
        if isinstance(method, DeleteMessage):
            out = self._find(method.chat_id, method.message_id)
            if out is not None:
                out.deleted = True
            return True
        return True


@dataclass
class Harness:
    bot: Bot
    dp: Dispatcher
    tg: FakeTelegram
    _update_id: int = 0
    _msg_id: int = 0
    answered: list = field(default_factory=list)

    @staticmethod
    def _user(uid: int) -> dict:
        return {"id": uid, "is_bot": False, "first_name": "Иван", "username": f"user{uid}"}

    async def _feed(self, payload: dict) -> None:
        self._update_id += 1
        update = Update.model_validate({"update_id": self._update_id, **payload}, context={"bot": self.bot})
        await self.dp.feed_update(self.bot, update)

    async def send(self, uid: int, text: str) -> None:
        self._msg_id += 1
        msg = {"message_id": self._msg_id, "date": int(time.time()), "chat": {"id": uid, "type": "private"},
               "from": self._user(uid), "text": text}
        if text.startswith("/"):
            msg["entities"] = [{"type": "bot_command", "offset": 0, "length": len(text.split()[0])}]
        await self._feed({"message": msg})

    async def send_contact(self, uid: int, phone: str) -> None:
        self._msg_id += 1
        await self._feed({"message": {
            "message_id": self._msg_id, "date": int(time.time()), "chat": {"id": uid, "type": "private"},
            "from": self._user(uid), "contact": {"phone_number": phone, "first_name": "Иван", "user_id": uid},
        }})

    async def press(self, uid: int, out: Out, data: str) -> None:
        await self._feed({"callback_query": {
            "id": f"cb{self._update_id + 1}", "from": self._user(uid), "chat_instance": "ci", "data": data,
            "message": {"message_id": out.message_id, "date": int(time.time()),
                        "chat": {"id": out.chat_id, "type": "private"},
                        "from": {"id": self.bot.id, "is_bot": True, "first_name": "bot"}, "text": out.text or "."},
        }})

    # --- исходящие
    def visible(self, chat_id: int) -> list[Out]:
        return [o for o in self.tg.outbox if o.chat_id == chat_id and not o.deleted]

    def last(self, chat_id: int) -> Out:
        msgs = self.visible(chat_id)
        assert msgs, f"в чате {chat_id} нет сообщений"
        return max(msgs, key=lambda o: o.tick)

    def last_text(self, chat_id: int) -> str:
        return self.last(chat_id).text or ""

    def all_text(self, chat_id: int) -> str:
        return "\n---\n".join(o.text or "" for o in self.visible(chat_id))

    @staticmethod
    def inline_buttons(out: Out) -> list:
        if isinstance(out.markup, InlineKeyboardMarkup):
            return [b for row in out.markup.inline_keyboard for b in row]
        return []

    def reply_kb_texts(self, chat_id: int) -> list[str]:
        """Тексты кнопок ПОСЛЕДНЕЙ постоянной клавиатуры, отправленной пользователю."""
        for out in sorted(self.visible(chat_id), key=lambda o: -o.tick):
            if isinstance(out.markup, ReplyKeyboardMarkup):
                return [b.text for row in out.markup.keyboard for b in row]
        return []

    async def click(self, uid: int, part: str) -> Out:
        for out in sorted(self.visible(uid), key=lambda o: -o.tick):
            for b in self.inline_buttons(out):
                if part in b.text and b.callback_data:
                    await self.press(uid, out, b.callback_data)
                    return out
        have = [b.text for o in self.visible(uid) for b in self.inline_buttons(o)]
        raise AssertionError(f"кнопка «{part}» не найдена. Есть: {have}")

    async def click_data(self, uid: int, startswith: str, *, not_contains: str = "") -> Out:
        out = self.last(uid)
        for b in self.inline_buttons(out):
            if b.callback_data and b.callback_data.startswith(startswith) and (not not_contains or not_contains not in b.callback_data):
                await self.press(uid, out, b.callback_data)
                return out
        raise AssertionError(f"нет кнопки с data {startswith!r}")


@pytest_asyncio.fixture
async def h():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    await generate_schedule()
    tg = FakeTelegram()
    bot = Bot(token=os.environ["BOT_TOKEN"], session=tg, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    # Роутеры — модульные синглтоны: перед каждым тестом отцепляем их от прошлого Dispatcher.
    from handlers import admin, booking, contacts, menu, profile, services, start
    for module in (menu, admin, booking, profile, services, contacts, start):
        module.router._parent_router = None
    register_all_handlers(dp)
    yield Harness(bot=bot, dp=dp, tg=tg)
    if scheduler.running:
        for job in scheduler.get_jobs():
            job.remove()
