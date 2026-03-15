import asyncio
from asyncio import Task
import logging
from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

import app.seen as seen
from app.config import settings
from app.core.apartment import ApartmentFilter
from app.core.enums import SocialStatus
from app.db.services import (
    apply_range_update,
    apply_status_update,
    build_default_filter,
    load_filter,
    preview_apartment,
    save_filter,
)
from app.labels import TRANSLATIONS
from app.telegram.notifier import TelegramNotifier

logger = logging.getLogger(__name__)
router = Router()


def translate(key: str, **kwargs: Any) -> str:
    lang = settings.BOT_LANGUAGE
    result = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key) or TRANSLATIONS[
        "en"
    ].get(key, key)
    return result.format(**kwargs) if kwargs else result


def parse_range_args(raw_args: list[str]) -> list[str]:
    combined = " ".join(raw_args)
    for dash in ("–", "—", "-"):
        combined = combined.replace(dash, " ")
    return [p for p in combined.split() if p]


class FilterStore:
    def __init__(
        self,
        chat_id: str,
        initial_filter: ApartmentFilter | None = None,
        initial_paused: bool = False,
    ):
        self._chat_id = chat_id
        self._filter = initial_filter or build_default_filter()
        self._paused = initial_paused

    @property
    def current_filter(self) -> ApartmentFilter:
        return self._filter

    @property
    def is_paused(self) -> bool:
        return self._paused

    def set_paused(self, paused: bool) -> None:
        self._paused = paused
        asyncio.ensure_future(save_filter(self._chat_id, self._filter, paused))

    def reset_to_defaults(self) -> None:
        self._filter = build_default_filter()
        self._paused = False
        asyncio.ensure_future(save_filter(self._chat_id, self._filter, self._paused))


class UserRegistry:
    def __init__(self) -> None:
        self._stores: dict[str, FilterStore] = {}
        self._lock = asyncio.Lock()

    async def get_or_create(self, chat_id: str) -> FilterStore:
        async with self._lock:
            if chat_id in self._stores:
                return self._stores[chat_id]
            saved = await load_filter(chat_id)
            if saved:
                filt, paused = saved
            else:
                filt, paused = build_default_filter(), False
            store = FilterStore(chat_id, filt, paused)
            self._stores[chat_id] = store
            logger.info("Registered chat_id=%s", chat_id)
            return store

    def all_stores(self) -> list[tuple[str, FilterStore]]:
        return list(self._stores.items())


_preview_tasks: dict[str, Task[None]] = {}


def _start_preview(
    chat_id: str,
    store: FilterStore,
    notifier: TelegramNotifier,
) -> None:
    existing = _preview_tasks.get(chat_id)
    if existing and not existing.done():
        existing.cancel()

    task = asyncio.create_task(_run_preview(chat_id, store, notifier))
    _preview_tasks[chat_id] = task

    def _remove_task(_: Any) -> None:
        _preview_tasks.pop(chat_id, None)

    task.add_done_callback(_remove_task)


async def _run_preview(
    chat_id: str,
    store: FilterStore,
    notifier: TelegramNotifier,
) -> None:
    from app.parsers.site import ALL_SCRAPERS

    scrapers = [cls() for cls in ALL_SCRAPERS]
    results = await asyncio.gather(
        *[s.fetch_all() for s in scrapers], return_exceptions=True
    )

    await asyncio.gather(*[s.close_session() for s in scrapers])

    found = 0
    for result in results:
        if isinstance(result, BaseException):
            logger.error("preview error: %s", result)
            continue

        for apt in result:
            if seen.is_already_notified(apt.id):
                continue
            sent = await preview_apartment(
                apt, store.current_filter, notifier, int(chat_id)
            )
            if sent:
                seen.mark_notified(apt.id)
                found += 1
                await asyncio.sleep(0.5)

    if found == 0:
        await notifier.send_text(int(chat_id), translate("preview_none"))


async def _after_update(
    message: Message,
    ok: bool,
    store: FilterStore,
    notifier: TelegramNotifier,
) -> None:
    if not ok:
        await message.answer(translate("invalid_value"))
        return
    chat_id = str(message.chat.id)

    cleared_count = seen.reset_notified()
    logger.info(
        "Filter changed: cleared %d processed IDs for re-evaluation", cleared_count
    )

    msg_text = (
        translate("filter_updated")
        + "\n\n"
        + store.current_filter.summary(settings.BOT_LANGUAGE)
    )
    await message.answer(msg_text)

    if not store.is_paused:
        await message.answer(translate("preview_searching"))
        _start_preview(chat_id, store, notifier)


@router.message(Command("start", "help"))
async def cmd_help(message: Message, registry: UserRegistry) -> None:
    await registry.get_or_create(str(message.chat.id))
    await message.answer(translate("help"))


@router.message(Command("filter"))
async def cmd_filter(message: Message, registry: UserRegistry) -> None:
    store = await registry.get_or_create(str(message.chat.id))
    await message.answer(store.current_filter.summary(settings.BOT_LANGUAGE))


@router.message(Command("rooms"))
async def cmd_rooms(
    message: Message,
    registry: UserRegistry,
    notifier: TelegramNotifier,
) -> None:
    chat_id = str(message.chat.id)
    store = await registry.get_or_create(chat_id)
    text = message.text or ""
    args = parse_range_args(text.split()[1:])
    ok = await apply_range_update(store.current_filter, chat_id, "rooms", args, int)
    await _after_update(message, ok, store, notifier)


@router.message(Command("price"))
async def cmd_price(
    message: Message,
    registry: UserRegistry,
    notifier: TelegramNotifier,
) -> None:
    chat_id = str(message.chat.id)
    store = await registry.get_or_create(chat_id)
    text = message.text or ""
    args = parse_range_args(text.split()[1:])
    ok = await apply_range_update(store.current_filter, chat_id, "price", args, float)
    await _after_update(message, ok, store, notifier)


@router.message(Command("area"))
async def cmd_area(
    message: Message,
    registry: UserRegistry,
    notifier: TelegramNotifier,
) -> None:
    chat_id = str(message.chat.id)
    store = await registry.get_or_create(chat_id)
    text = message.text or ""
    args = parse_range_args(text.split()[1:])
    ok = await apply_range_update(store.current_filter, chat_id, "area", args, float)
    await _after_update(message, ok, store, notifier)


@router.message(Command("status"))
async def cmd_status(
    message: Message,
    registry: UserRegistry,
    notifier: TelegramNotifier,
) -> None:
    chat_id = str(message.chat.id)
    store = await registry.get_or_create(chat_id)
    text = message.text or ""
    parts = text.split()
    raw = parts[1].lower() if len(parts) > 1 else ""
    try:
        status = SocialStatus(raw)
    except ValueError:
        await message.answer(translate("status_options"))
        return
    ok = await apply_status_update(store.current_filter, chat_id, status)
    await _after_update(message, ok, store, notifier)


@router.message(Command("pause"))
async def cmd_pause(message: Message, registry: UserRegistry) -> None:
    store = await registry.get_or_create(str(message.chat.id))
    store.set_paused(True)
    await message.answer(translate("paused"))


@router.message(Command("resume"))
async def cmd_resume(
    message: Message,
    registry: UserRegistry,
    notifier: TelegramNotifier,
) -> None:
    chat_id = str(message.chat.id)
    store = await registry.get_or_create(chat_id)

    if store.is_paused:
        store.set_paused(False)
        await message.answer(translate("resumed"))
        await message.answer(translate("preview_searching"))
        _start_preview(chat_id, store, notifier)
    else:
        await message.answer(translate("resumed"))


@router.message(Command("reset"))
async def cmd_reset(
    message: Message,
    registry: UserRegistry,
    notifier: TelegramNotifier,
) -> None:
    chat_id = str(message.chat.id)
    store = await registry.get_or_create(chat_id)
    store.reset_to_defaults()
    cleared = seen.clear_processed()
    logger.info(
        "[%s] Filters reset. Cleared %d IDs for re-evaluation", chat_id, cleared
    )

    summary = store.current_filter.summary(settings.BOT_LANGUAGE)
    await message.answer(f"{translate('reset_done')}\n\n{summary}")

    if not store.is_paused:
        await message.answer(translate("preview_searching"))
        _start_preview(chat_id, store, notifier)


@router.message(Command("lang"))
async def cmd_lang(message: Message) -> None:
    text = message.text or ""
    parts = text.split()
    if len(parts) < 2 or parts[1].lower() not in {"en", "ru"}:
        await message.answer(translate("lang_invalid"))
        return
    settings.BOT_LANGUAGE = parts[1].lower()
    await message.answer(translate("lang_changed"))


@router.message()
async def cmd_unknown(message: Message) -> None:
    if message.text and message.text.startswith("/"):
        await message.answer(translate("unknown_cmd"))
