import asyncio
import logging
import time
from typing import Any

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import settings
from app.core.enums import SocialStatus
from app.db.services import ListingService, FilterService
from app.db.session import db
from app.labels import TRANSLATIONS
from app.telegram.notifier import TelegramNotifier
from app.telegram.handlers import FilterStore, UserRegistry
from app.parsers.site import ALL_SCRAPERS

logger = logging.getLogger(__name__)

class BotController:
    def __init__(self, registry: UserRegistry, notifier: TelegramNotifier):
        self.registry = registry
        self.notifier = notifier
        self.listing_svc = ListingService()
        self.filter_svc = FilterService()
        self._preview_tasks: dict[str, asyncio.Task[None]] = {}

    def translate(self, key: str, **kwargs: Any) -> str:
        lang = settings.BOT_LANGUAGE
        result = TRANSLATIONS.get(lang, TRANSLATIONS["en"]).get(key) or \
                 TRANSLATIONS["en"].get(key, key)
        return result.format(**kwargs) if kwargs else result

    def parse_range_args(self, text: str) -> list[str]:
        args = text.split()[1:]
        combined = " ".join(args)
        for dash in ("–", "—", "-"):
            combined = combined.replace(dash, " ")
        return [p for p in combined.split() if p]

    def start_preview(self, chat_id: str, store: FilterStore) -> None:
        existing = self._preview_tasks.get(chat_id)
        if existing and not existing.done():
            existing.cancel()

        task = asyncio.create_task(self._run_preview(chat_id, store))
        self._preview_tasks[chat_id] = task
        task.add_done_callback(lambda _: self._preview_tasks.pop(chat_id, None))

    async def _run_preview(self, chat_id: str, store: FilterStore) -> None:
        start_time = time.perf_counter()
        found = 0
        scrapers = [cls() for cls in ALL_SCRAPERS]
        
        for scraper in scrapers:
            try:
                apartments = await scraper.fetch_all()
                if not apartments:
                    continue

                async with db.session_context():
                    for apt in apartments:
                        sent = await self.listing_svc.preview_apartment(
                            apt, store.current_filter, self.notifier, int(chat_id)
                        )
                        if sent:
                            found += 1
                            await asyncio.sleep(0.4)
                            
                logger.info("[%s] preview: processed %d apartments", scraper.slug, len(apartments))
            
            except Exception as exc:
                logger.error("[%s] preview error: %s", scraper.slug, exc)
            
            finally:
                await scraper.close_session()

        duration = time.perf_counter() - start_time
        logger.info("Preview for %s finished in %.2fs. Found: %d", chat_id, duration, found)

        if found == 0:
            await self.notifier.send_text(int(chat_id), self.translate("preview_none"))

    async def finalize_update(self, message: Message, ok: bool, store: FilterStore) -> None:
        if not ok:
            await message.answer(self.translate("invalid_value"))
            return
        
        summary = store.current_filter.summary(settings.BOT_LANGUAGE)
        await message.answer(f"{self.translate('filter_updated')}\n\n{summary}")

        if not store.is_paused:
            await message.answer(self.translate("preview_searching"))
            self.start_preview(str(message.chat.id), store)


class CommandHandlers:
    def __init__(self, controller: BotController):
        self.ctrl = controller

    async def cmd_help(self, message: Message) -> None:
        await self.ctrl.registry.get_or_create(str(message.chat.id))
        await message.answer(self.ctrl.translate("help"))

    async def cmd_filter(self, message: Message) -> None:
        store = await self.ctrl.registry.get_or_create(str(message.chat.id))
        await message.answer(store.current_filter.summary(settings.BOT_LANGUAGE))

    async def cmd_rooms(self, message: Message) -> None:
        chat_id = str(message.chat.id)
        store = await self.ctrl.registry.get_or_create(chat_id)
        args = self.ctrl.parse_range_args(message.text or "")
        async with db.session_context():
            ok = await self.ctrl.filter_svc.apply_range_update(store.current_filter, chat_id, "rooms", args, int)
        await self.ctrl.finalize_update(message, ok, store)

    async def cmd_price(self, message: Message) -> None:
        chat_id = str(message.chat.id)
        store = await self.ctrl.registry.get_or_create(chat_id)
        args = self.ctrl.parse_range_args(message.text or "")
        async with db.session_context():
            ok = await self.ctrl.filter_svc.apply_range_update(store.current_filter, chat_id, "price", args, float)
        await self.ctrl.finalize_update(message, ok, store)

    async def cmd_area(self, message: Message) -> None:
        chat_id = str(message.chat.id)
        store = await self.ctrl.registry.get_or_create(chat_id)
        args = self.ctrl.parse_range_args(message.text or "")
        async with db.session_context():
            ok = await self.ctrl.filter_svc.apply_range_update(store.current_filter, chat_id, "area", args, float)
        await self.ctrl.finalize_update(message, ok, store)

    async def cmd_status(self, message: Message) -> None:
        chat_id = str(message.chat.id)
        store = await self.ctrl.registry.get_or_create(chat_id)
        parts = (message.text or "").split()
        raw = parts[1].lower() if len(parts) > 1 else ""
        try:
            status = SocialStatus(raw)
            async with db.session_context():
                ok = await self.ctrl.filter_svc.apply_status_update(store.current_filter, chat_id, status)
            await self.ctrl.finalize_update(message, ok, store)
        except ValueError:
            await message.answer(self.ctrl.translate("status_options"))

    async def cmd_pause(self, message: Message) -> None:
        store = await self.ctrl.registry.get_or_create(str(message.chat.id))
        store.set_paused(True)
        await message.answer(self.ctrl.translate("paused"))

    async def cmd_resume(self, message: Message) -> None:
        chat_id = str(message.chat.id)
        store = await self.ctrl.registry.get_or_create(chat_id)
        if store.is_paused:
            store.set_paused(False)
            await message.answer(self.ctrl.translate("resumed"))
            await message.answer(self.ctrl.translate("preview_searching"))
            self.ctrl.start_preview(chat_id, store)
        else:
            await message.answer(self.ctrl.translate("resumed"))

    async def cmd_reset(self, message: Message) -> None:
        chat_id = str(message.chat.id)
        store = await self.ctrl.registry.get_or_create(chat_id)
        store.reset_to_defaults() 
        async with db.session_context():
            await self.ctrl.listing_svc.reset_user_history(chat_id)
        await message.answer(f"{self.ctrl.translate('reset_done')}\n\n{store.current_filter.summary(settings.BOT_LANGUAGE)}")
        if not store.is_paused:
            self.ctrl.start_preview(chat_id, store)

    async def cmd_lang(self, message: Message) -> None:
        parts = (message.text or "").split()
        if len(parts) < 2 or parts[1].lower() not in {"en", "ru"}:
            await message.answer(self.ctrl.translate("lang_invalid"))
            return
        settings.BOT_LANGUAGE = parts[1].lower()
        await message.answer(self.ctrl.translate("lang_changed"))

    async def cmd_unknown(self, message: Message) -> None:
        if message.text and message.text.startswith("/"):
            await message.answer(self.ctrl.translate("unknown_cmd"))


def setup_router(registry: UserRegistry, notifier: TelegramNotifier) -> Router:
    ctrl = BotController(registry, notifier)
    h = CommandHandlers(ctrl)
    router = Router()
    
    router.message.register(h.cmd_help, Command("start", "help"))
    router.message.register(h.cmd_filter, Command("filter"))
    router.message.register(h.cmd_rooms, Command("rooms"))
    router.message.register(h.cmd_price, Command("price"))
    router.message.register(h.cmd_area, Command("area"))
    router.message.register(h.cmd_status, Command("status"))
    router.message.register(h.cmd_pause, Command("pause"))
    router.message.register(h.cmd_resume, Command("resume"))
    router.message.register(h.cmd_reset, Command("reset"))
    router.message.register(h.cmd_lang, Command("lang"))
    router.message.register(h.cmd_unknown)
    
    return router