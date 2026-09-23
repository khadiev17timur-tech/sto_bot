"""Инициализация асинхронного движка SQLAlchemy и фабрики сессий."""
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import DB_PATH
from database.models import Base

os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

# timeout — сколько секунд соединение будет ждать освобождения блокировки записи
# перед тем, как поднять ошибку "database is locked". Это ключевая настройка для
# корректной работы при конкурентных попытках бронирования одного слота.
engine = create_async_engine(
    f"sqlite+aiosqlite:///{DB_PATH}",
    connect_args={"timeout": 15},
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=15000")
    cursor.close()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session
