from __future__ import annotations

import pytest
from aiohttp.test_utils import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.models import ExtensionPairing, User
from app.realtime.pairing import PairingStore


async def create_profiled_user(
    session: AsyncSession, chat_id: str, user_id: int
) -> User:
    user = User(
        id=user_id,
        chat_id=chat_id,
        username="asho",
        full_name="Asho Case",
        first_name="Asho",
        last_name="Case",
        salutation="Herr",
        email="asho@example.com",
        phone="+49123456789",
        street="Teststrasse",
        house_number="1",
        zip_code="10115",
        city="Berlin",
        persons_total=2,
        wbs_available=True,
        wbs_rooms=2,
        wbs_income=100,
        wbs_date="01.04.2026",
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_pair_endpoint_returns_profile_and_invalidates_pin(
    aiohttp_client: TestClient,
    db_session: AsyncSession,
    pairing_store: PairingStore,
) -> None:
    await create_profiled_user(db_session, "2001", 2001)
    pin = await pairing_store.create_pin("2001")

    response = await aiohttp_client.post("/api/pair", json={"pin": pin})
    payload = await response.json()

    assert response.status == 200
    assert payload["chatId"] == "2001"
    assert payload["chat_id"] == "2001"
    assert payload["token"]
    assert payload["profile"] == {
        "salutation": "Herr",
        "first_name": "Asho",
        "last_name": "Case",
        "email": "asho@example.com",
        "phone": "+49123456789",
        "street": "Teststrasse",
        "house_number": "1",
        "zip_code": "10115",
        "city": "Berlin",
        "persons_total": 2,
        "wbs_available": True,
        "wbs_date": "01.04.2026",
        "wbs_rooms": 2,
        "wbs_income": 100,
    }

    user = (
        await db_session.execute(select(User).where(User.chat_id == "2001"))
    ).scalar_one()
    pairing = (
        await db_session.execute(
            select(ExtensionPairing).where(ExtensionPairing.chat_id == "2001")
        )
    ).scalar_one()

    assert user.pairing_pin is None
    assert pairing.consumed_at is not None
    assert pairing.token == payload["token"]


@pytest.mark.asyncio
async def test_pair_endpoint_rejects_invalid_pin(aiohttp_client: TestClient) -> None:
    response = await aiohttp_client.post("/api/pair", json={"pin": "999999"})
    payload = await response.json()

    assert response.status == 404
    assert payload == {"error": "pin is invalid or expired"}


@pytest.mark.asyncio
async def test_pair_endpoint_requires_pin(aiohttp_client: TestClient) -> None:
    response = await aiohttp_client.post("/api/pair", json={})
    payload = await response.json()

    assert response.status == 400
    assert payload == {"error": "pin is required"}
