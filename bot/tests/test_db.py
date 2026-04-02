from __future__ import annotations

import datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.models import ExtensionPairing, User
from app.realtime.pairing import PairingStore


async def create_user(
    session: AsyncSession, chat_id: str, user_id: int, **overrides
) -> User:
    user = User(
        id=user_id,
        chat_id=chat_id,
        username=overrides.get("username"),
        full_name=overrides.get("full_name"),
        first_name=overrides.get("first_name", "Asho"),
        last_name=overrides.get("last_name", "Case"),
        email=overrides.get("email", "asho@example.com"),
        pairing_pin=overrides.get("pairing_pin"),
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_user_model_persists_profile_fields_and_pairing_pin(
    db_session: AsyncSession,
) -> None:
    await create_user(
        db_session,
        "1001",
        1001,
        username="asho",
        full_name="Asho Case",
        first_name="Asho",
        last_name="Case",
        email="asho@example.com",
        pairing_pin="123456",
    )

    result = await db_session.execute(select(User).where(User.chat_id == "1001"))
    user = result.scalar_one()

    assert user.username == "asho"
    assert user.full_name == "Asho Case"
    assert user.first_name == "Asho"
    assert user.last_name == "Case"
    assert user.email == "asho@example.com"
    assert user.pairing_pin == "123456"


@pytest.mark.asyncio
async def test_user_chat_id_must_be_unique(db_session: AsyncSession) -> None:
    await create_user(db_session, "1002", 1002)

    duplicate = User(
        id=1003,
        chat_id="1002",
        first_name="Other",
        last_name="User",
    )
    db_session.add(duplicate)

    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_extension_pairing_pin_code_must_be_unique(
    db_session: AsyncSession,
) -> None:
    await create_user(db_session, "1004", 1004)
    await create_user(db_session, "1005", 1005)

    first = ExtensionPairing(
        id=1,
        chat_id="1004",
        pin_code="654321",
        pin_expires_at=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=5),
    )
    second = ExtensionPairing(
        id=2,
        chat_id="1005",
        pin_code="654321",
        pin_expires_at=datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(minutes=5),
    )
    db_session.add_all([first, second])

    with pytest.raises(IntegrityError):
        await db_session.flush()

    await db_session.rollback()


@pytest.mark.asyncio
async def test_pairing_store_saves_pairing_pin_on_user(
    db_session: AsyncSession, pairing_store: PairingStore
) -> None:
    await create_user(db_session, "1006", 1006)

    pin = await pairing_store.create_pin("1006")

    result = await db_session.execute(select(User).where(User.chat_id == "1006"))
    user = result.scalar_one()

    assert pin.isdigit()
    assert len(pin) == 6
    assert user.pairing_pin == pin
