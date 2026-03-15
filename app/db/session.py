import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import AsyncGenerator, Optional
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from app.config import settings
from app.db.models.base import Base

logger = logging.getLogger(__name__)
_session_var: ContextVar[Optional[AsyncSession]] = ContextVar[AsyncSession | None](
    "_session_var", default=None
)


def get_session() -> AsyncSession:
    session = _session_var.get()
    if session is None:
        raise RuntimeError(
            "No database session in context. "
            "Wrap your code with async with session_context():"
        )
    return session


class DatabaseManager:
    def __init__(self) -> None:
        self._engine: Optional[AsyncEngine] = None
        self._factory: Optional[async_sessionmaker[AsyncSession]] = None

    async def init(self) -> None:
        self._engine = create_async_engine(
            settings.DATABASE_URL_asyncpg,
            **settings.engine_options,
        )
        self._factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info(
            "Database ready: %s@%s:%s/%s",
            settings.DB_USER,
            settings.DB_HOST,
            settings.DB_PORT,
            settings.DB_NAME,
        )

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            logger.info("Database engine disposed")

    @asynccontextmanager
    async def session_context(self) -> AsyncGenerator[AsyncSession, None]:
        if self._factory is None:
            raise RuntimeError(
                "DatabaseManager not initialised — call await db.init() first"
            )

        session: AsyncSession = self._factory()
        token = _session_var.set(session)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
            _session_var.reset(token)

    @asynccontextmanager
    async def nested_transaction(self) -> AsyncGenerator[AsyncSession, None]:
        session = get_session()
        async with session.begin_nested():
            yield session


db = DatabaseManager()
