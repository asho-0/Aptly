from __future__ import annotations

import os
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
import pytest_asyncio
from aiogram import Bot
from aiohttp.test_utils import TestClient, TestServer
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.apartment import Apartment, ApartmentFilter
from app.core.config import settings
from app.core.enums import SocialStatus
from app.db.session import _session_var, db
from app.db.utils import create_database, drop_database, run_migrations
from app.http.server import ApiServer
from app.realtime import ExtensionGateway, PairingStore
from app.telegram.notifier import TelegramNotifier


def make_filter(**kwargs) -> ApartmentFilter:
    defaults = dict(
        min_rooms=1,
        max_rooms=3,
        min_sqm=20,
        max_sqm=80,
        min_price=200,
        max_price=1000,
        social_status=SocialStatus.ANY,
    )
    return ApartmentFilter(**{**defaults, **kwargs})


def make_apartment(**kwargs) -> Apartment:
    defaults = dict(
        id="degewo:123",
        source="Degewo",
        url="https://example.com/apt/123",
        title="Test Wohnung",
        price=600.0,
        rooms=2.0,
        sqm=50.0,
        social_status=SocialStatus.ANY,
    )
    return Apartment(**{**defaults, **kwargs})


@pytest.fixture
def complete_filter() -> ApartmentFilter:
    return make_filter()


@pytest.fixture
def incomplete_filter() -> ApartmentFilter:
    return ApartmentFilter(
        min_rooms=None,
        max_rooms=None,
        min_sqm=None,
        max_sqm=None,
        min_price=None,
        max_price=None,
        social_status=SocialStatus.ANY,
    )


@pytest.fixture
def basic_apartment() -> Apartment:
    return make_apartment()


@pytest.fixture(scope="session")
def postgres_test_database() -> str:
    original_db_name = settings.DB_NAME
    original_env_db_name = os.environ.get("DB_NAME")
    test_db_name = f"{original_db_name}_pytest_{uuid4().hex[:8]}"

    os.environ["DB_NAME"] = test_db_name
    settings.DB_NAME = test_db_name
    create_database(test_db_name)
    run_migrations(settings.DATABASE_URL_psycopg)

    try:
        yield test_db_name
    finally:
        drop_database(test_db_name)
        settings.DB_NAME = original_db_name
        if original_env_db_name is None:
            os.environ.pop("DB_NAME", None)
        else:
            os.environ["DB_NAME"] = original_env_db_name


@pytest_asyncio.fixture(scope="session")
async def db_engine(postgres_test_database: str) -> AsyncEngine:
    engine = create_async_engine(
        settings.DATABASE_URL_asyncpg,
        **settings.engine_options,
    )
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine):
    async with db_engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)

        @asynccontextmanager
        async def session_context():
            token = _session_var.set(session)
            try:
                yield session
                await session.flush()
            finally:
                _session_var.reset(token)

        @asynccontextmanager
        async def nested_transaction():
            token = _session_var.set(session)
            try:
                async with session.begin_nested():
                    yield session
            finally:
                _session_var.reset(token)

        original_engine = db._engine
        original_factory = db._factory
        original_session_context = db.session_context
        original_nested_transaction = db.nested_transaction

        db._engine = db_engine
        db._factory = async_sessionmaker(
            bind=connection,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
        db.session_context = session_context
        db.nested_transaction = nested_transaction

        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()
            db._engine = original_engine
            db._factory = original_factory
            db.session_context = original_session_context
            db.nested_transaction = original_nested_transaction


@pytest.fixture
def mocked_bot(mocker) -> Bot:
    bot = mocker.AsyncMock(spec=Bot)
    bot.send_message = mocker.AsyncMock()
    bot.send_photo = mocker.AsyncMock()
    bot.edit_message_text = mocker.AsyncMock()
    bot.edit_message_caption = mocker.AsyncMock()
    bot.edit_message_reply_markup = mocker.AsyncMock()
    bot.pin_chat_message = mocker.AsyncMock()
    return bot


@pytest.fixture
def notifier(mocked_bot: Bot) -> TelegramNotifier:
    return TelegramNotifier(mocked_bot)


@pytest.fixture
def pairing_store() -> PairingStore:
    return PairingStore()


@pytest.fixture
def extension_gateway(
    notifier: TelegramNotifier, pairing_store: PairingStore
) -> ExtensionGateway:
    return ExtensionGateway(notifier, pairing_store)


@pytest.fixture
def api_server(
    extension_gateway: ExtensionGateway, pairing_store: PairingStore
) -> ApiServer:
    return ApiServer(extension_gateway, pairing_store)


@pytest_asyncio.fixture
async def aiohttp_client(db_session: AsyncSession, api_server: ApiServer):
    server = TestServer(api_server._app)
    client = TestClient(server)
    await client.start_server()
    try:
        yield client
    finally:
        await client.close()
