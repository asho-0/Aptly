from __future__ import annotations
from types import SimpleNamespace

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.models import User
from app.db.services import UserService
from app.db.session import db
from app.telegram.handlers.commands_handler import (
    BotController,
    CallbackHandlers,
    ProfileStates,
)


def build_state() -> FSMContext:
    return FSMContext(
        storage=MemoryStorage(),
        key=StorageKey(bot_id=1, chat_id=123, user_id=123),
    )


def build_controller(mocker, registry=None):
    resolved_registry = registry or mocker.Mock()
    resolved_registry.get_or_create = mocker.AsyncMock(
        return_value=SimpleNamespace(lang="en")
    )
    notifier = mocker.Mock()
    extension_gateway = mocker.Mock()
    extension_gateway.push_profile = mocker.AsyncMock(return_value=True)
    pairing_store = mocker.Mock()
    controller = BotController(
        resolved_registry, notifier, extension_gateway, pairing_store
    )
    return controller


async def ensure_user(chat_id: str) -> User:
    async with db.session_context():
        return await UserService().get_or_register_user(chat_id, "tester", "Test User")


@pytest.mark.asyncio
async def test_link_extension_generates_pin_and_sends_it_to_user(mocker) -> None:
    controller = build_controller(mocker)
    controller.pairing_store.create_pin = mocker.AsyncMock(return_value="123456")
    callbacks = CallbackHandlers(controller)

    message = mocker.Mock()
    message.chat.id = 123
    message.answer = mocker.AsyncMock()

    callback = mocker.Mock()
    callback.answer = mocker.AsyncMock()

    mocker.patch(
        "app.telegram.handlers.commands_handler._require_message", return_value=message
    )

    await callbacks.cb_link_extension(callback)

    controller.pairing_store.create_pin.assert_awaited_once_with("123")
    message.answer.assert_awaited_once()
    assert "123456" in message.answer.await_args.args[0]
    assert message.answer.await_args.kwargs["parse_mode"] == "HTML"
    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_profile_text_advances_to_next_state_for_text_field(mocker) -> None:
    controller = build_controller(mocker)
    callbacks = CallbackHandlers(controller)
    state = build_state()

    await state.set_state(ProfileStates.first_name)

    message = mocker.Mock()
    message.chat.id = 123
    message.text = "Asho"
    message.answer = mocker.AsyncMock()

    await callbacks.handle_profile_text(message, state)

    assert await state.get_state() == ProfileStates.last_name.state
    assert (await state.get_data())["first_name"] == "Asho"


@pytest.mark.asyncio
async def test_profile_text_persists_profile_and_broadcasts_update(
    mocker,
    db_session: AsyncSession,
) -> None:
    controller = build_controller(mocker)
    callbacks = CallbackHandlers(controller)
    state = build_state()

    await ensure_user("123")
    await state.set_state(ProfileStates.wbs_income)
    await state.update_data(
        salutation="Herr",
        first_name="Asho",
        last_name="Case",
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

    message = mocker.Mock()
    message.chat.id = 123
    message.answer = mocker.AsyncMock()
    callback = mocker.Mock()
    callback.data = "profile_income:100"
    callback.message = message
    callback.answer = mocker.AsyncMock()

    await callbacks.handle_profile_income(callback, state)

    user = (
        await db_session.execute(select(User).where(User.chat_id == "123"))
    ).scalar_one()

    assert user.first_name == "Asho"
    assert user.last_name == "Case"
    assert user.salutation == "Herr"
    assert user.email == "asho@example.com"
    assert user.phone == "+49123456789"
    assert user.street == "Teststrasse"
    assert user.house_number == "1"
    assert user.zip_code == "10115"
    assert user.city == "Berlin"
    assert user.persons_total == 2
    assert user.wbs_available is True
    assert user.wbs_rooms == 2
    assert user.wbs_income == 100
    assert user.wbs_date == "01.04.2026"
    assert await state.get_state() is None
    controller.extension_gateway.push_profile.assert_awaited_once_with(
        "123",
        {
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
        },
    )


@pytest.mark.asyncio
async def test_profile_text_accepts_german_wbs_date_format(mocker) -> None:
    controller = build_controller(mocker)
    callbacks = CallbackHandlers(controller)
    state = build_state()

    await state.set_state(ProfileStates.wbs_date)

    message = mocker.Mock()
    message.chat.id = 123
    message.text = "20.12.2026"
    message.answer = mocker.AsyncMock()

    await callbacks.handle_profile_text(message, state)

    assert await state.get_state() == ProfileStates.wbs_rooms.state
    assert (await state.get_data())["wbs_date"] == "20.12.2026"
