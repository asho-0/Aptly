import time
import logging
from typing import Any

import asyncio
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from app.core.config import settings
from app.core.enums import SocialStatus
from app.db.services import ListingService, FilterService
from app.db.session import db
from app.telegram.interface.labels import TRANSLATIONS
from app.telegram.notifier import TelegramNotifier
from app.telegram.handlers import FilterStore, UserRegistry
from app.telegram.interface.keyboards import (
    main_menu_keyboard,
    rooms_keyboard,
    price_keyboard,
    area_keyboard,
    status_keyboard,
)
from app.parsers.site import ALL_SCRAPERS

logger = logging.getLogger(__name__)


def _require_message(cb: CallbackQuery) -> Message:
    if not isinstance(cb.message, Message):
        raise ValueError("No accessible message in callback")
    return cb.message


class BotController:
    def __init__(self, registry: UserRegistry, notifier: TelegramNotifier):
        self.registry = registry
        self.notifier = notifier
        self.listing_svc = ListingService()
        self.filter_svc = FilterService()
        self._preview_tasks: dict[str, asyncio.Task[None]] = {}

    def translate(self, key: str, lang: str | None = None, **kwargs: Any) -> str:
        resolved = lang or "en"
        result = TRANSLATIONS.get(resolved, TRANSLATIONS["en"]).get(
            key
        ) or TRANSLATIONS["en"].get(key, key)
        return result.format(**kwargs) if kwargs else result

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

        try:
            results = await asyncio.gather(
                *[scraper.fetch_all() for scraper in scrapers],
                return_exceptions=True,
            )

            for scraper, result in zip(scrapers, results):
                if isinstance(result, BaseException):
                    logger.error("[%s] preview error: %s", scraper.slug, result)
                    continue

                apartments = result
                if not apartments:
                    continue

                async with db.session_context():
                    for apt in apartments:
                        sent = await self.listing_svc.preview_apartment(
                            apt,
                            store.current_filter,
                            self.notifier,
                            int(chat_id),
                            lang=store.lang,
                        )
                        if sent:
                            found += 1
                            await asyncio.sleep(settings.NOTIFICATION_DELAY)

                logger.info(
                    "[%s] preview: processed %d apartments",
                    scraper.slug,
                    len(apartments),
                )

        except asyncio.CancelledError:
            logger.info("Preview for %s was cancelled", chat_id)
            raise

        finally:
            for scraper in scrapers:
                await scraper.close_session()

        duration = time.perf_counter() - start_time
        logger.info(
            "Preview for %s finished in %.2fs. Found: %d", chat_id, duration, found
        )

        if found == 0:
            await self.notifier.send_text(
                int(chat_id), self.translate("preview_none", lang=store.lang)
            )


class CallbackHandlers:
    def __init__(self, controller: BotController):
        self.ctrl = controller

    async def _get_store(self, chat_id: str) -> FilterStore:
        return await self.ctrl.registry.get_or_create(chat_id)

    async def _apply_range(
        self, chat_id: str, field: str, lo: str, hi: str, cast_type: type
    ) -> bool:
        store = await self._get_store(chat_id)
        async with db.session_context():
            return await self.ctrl.filter_svc.apply_range_update(
                store.current_filter, chat_id, field, [lo, hi], cast_type
            )

    def _require_data(self, cb: CallbackQuery) -> str:
        if cb.data is None:
            raise ValueError("No data in callback")
        return cb.data

    async def _finish_preset(self, cb: CallbackQuery, ok: bool) -> None:
        msg = _require_message(cb)
        chat_id = str(msg.chat.id)
        store = await self._get_store(chat_id)
        lang = store.lang
        if not ok:
            await cb.answer(
                self.ctrl.translate("invalid_value", lang=lang), show_alert=True
            )
            return
        summary = store.current_filter.summary(lang)
        await msg.edit_text(
            f"{self.ctrl.translate('filter_updated', lang=lang)}\n\n{summary}",
            reply_markup=main_menu_keyboard(),
        )
        await cb.answer()
        if not store.is_paused and store.current_filter.is_complete():
            await msg.answer(self.ctrl.translate("preview_searching", lang=lang))
            self.ctrl.start_preview(chat_id, store)

    async def show_menu(self, message: Message) -> None:
        store = await self._get_store(str(message.chat.id))
        lang = store.lang
        summary = store.current_filter.summary(lang)
        sent = await message.answer(
            f"{summary}\n\n{self.ctrl.translate('menu_title', lang=lang)}",
            reply_markup=main_menu_keyboard(),
        )
        if message.bot:
            await message.bot.pin_chat_message(
                chat_id=message.chat.id,
                message_id=sent.message_id,
                disable_notification=True,
            )

    async def cb_back_menu(self, cb: CallbackQuery) -> None:
        msg = _require_message(cb)
        store = await self._get_store(str(msg.chat.id))
        lang = store.lang
        summary = store.current_filter.summary(lang)
        await msg.edit_text(
            f"{summary}\n\n{self.ctrl.translate('menu_title', lang=lang)}",
            reply_markup=main_menu_keyboard(),
        )
        await cb.answer()

    async def cb_menu_rooms(self, cb: CallbackQuery) -> None:
        msg = _require_message(cb)
        store = await self._get_store(str(msg.chat.id))
        await msg.edit_text(
            self.ctrl.translate("choose_rooms", lang=store.lang),
            reply_markup=rooms_keyboard(),
        )
        await cb.answer()

    async def cb_menu_price(self, cb: CallbackQuery) -> None:
        msg = _require_message(cb)
        store = await self._get_store(str(msg.chat.id))
        await msg.edit_text(
            self.ctrl.translate("choose_price", lang=store.lang),
            reply_markup=price_keyboard(),
        )
        await cb.answer()

    async def cb_menu_area(self, cb: CallbackQuery) -> None:
        msg = _require_message(cb)
        store = await self._get_store(str(msg.chat.id))
        await msg.edit_text(
            self.ctrl.translate("choose_area", lang=store.lang),
            reply_markup=area_keyboard(),
        )
        await cb.answer()

    async def cb_menu_status(self, cb: CallbackQuery) -> None:
        msg = _require_message(cb)
        store = await self._get_store(str(msg.chat.id))
        await msg.edit_text(
            self.ctrl.translate("choose_status", lang=store.lang),
            reply_markup=status_keyboard(),
        )
        await cb.answer()

    async def cb_rooms_preset(self, cb: CallbackQuery) -> None:
        msg = _require_message(cb)
        _, lo, hi = self._require_data(cb).split("_")
        ok = await self._apply_range(str(msg.chat.id), "rooms", lo, hi, int)
        await self._finish_preset(cb, ok)

    async def cb_price_preset(self, cb: CallbackQuery) -> None:
        msg = _require_message(cb)
        _, lo, hi = self._require_data(cb).split("_")
        ok = await self._apply_range(str(msg.chat.id), "price", lo, hi, float)
        await self._finish_preset(cb, ok)

    async def cb_area_preset(self, cb: CallbackQuery) -> None:
        msg = _require_message(cb)
        _, lo, hi = self._require_data(cb).split("_")
        ok = await self._apply_range(str(msg.chat.id), "area", lo, hi, float)
        await self._finish_preset(cb, ok)

    async def cb_status_value(self, cb: CallbackQuery) -> None:
        msg = _require_message(cb)
        chat_id = str(msg.chat.id)
        store = await self._get_store(chat_id)
        raw = self._require_data(cb).split("_")[1]
        try:
            status = SocialStatus(raw)
            async with db.session_context():
                ok = await self.ctrl.filter_svc.apply_status_update(
                    store.current_filter, chat_id, status
                )
            await self._finish_preset(cb, ok)
        except ValueError:
            await cb.answer(
                self.ctrl.translate("status_options", lang=store.lang), show_alert=True
            )

    async def cb_show_filter(self, cb: CallbackQuery) -> None:
        msg = _require_message(cb)
        store = await self._get_store(str(msg.chat.id))
        await msg.edit_text(
            store.current_filter.summary(store.lang),
            reply_markup=main_menu_keyboard(),
        )
        await cb.answer()

    async def cb_reset(self, cb: CallbackQuery) -> None:
        msg = _require_message(cb)
        chat_id = str(msg.chat.id)
        store = await self._get_store(chat_id)
        store.reset_to_defaults()
        async with db.session_context():
            await self.ctrl.listing_svc.reset_user_history(chat_id)
        lang = store.lang
        await msg.edit_text(
            f"{self.ctrl.translate('reset_done', lang=lang)}\n\n{store.current_filter.summary(lang)}",
            reply_markup=main_menu_keyboard(),
        )
        await cb.answer()
        if not store.is_paused and store.current_filter.is_complete():
            await msg.answer(self.ctrl.translate("preview_searching", lang=lang))
            self.ctrl.start_preview(chat_id, store)

    async def cb_pause(self, cb: CallbackQuery) -> None:
        msg = _require_message(cb)
        store = await self._get_store(str(msg.chat.id))
        store.set_paused(True)
        await cb.answer(self.ctrl.translate("paused", lang=store.lang), show_alert=True)

    async def cb_resume(self, cb: CallbackQuery) -> None:
        msg = _require_message(cb)
        chat_id = str(msg.chat.id)
        store = await self._get_store(chat_id)
        lang = store.lang
        store.set_paused(False)
        if not store.current_filter.is_complete():
            await cb.answer(
                self.ctrl.translate("filter_incomplete", lang=lang), show_alert=True
            )
            return
        self.ctrl.start_preview(chat_id, store)
        await cb.answer(self.ctrl.translate("resumed", lang=lang), show_alert=True)

    async def cb_lang(self, cb: CallbackQuery) -> None:
        new_lang = self._require_data(cb).split("_")[1]
        msg = _require_message(cb)
        store = await self._get_store(str(msg.chat.id))
        store.set_lang(new_lang)
        # Обновляем меню с новым языком сразу
        summary = store.current_filter.summary(new_lang)
        await msg.edit_text(
            f"{summary}\n\n{self.ctrl.translate('menu_title', lang=new_lang)}",
            reply_markup=main_menu_keyboard(),
        )
        await cb.answer(
            self.ctrl.translate("lang_changed", lang=new_lang), show_alert=True
        )


def setup_router(registry: UserRegistry, notifier: TelegramNotifier) -> Router:
    ctrl = BotController(registry, notifier)
    cb = CallbackHandlers(ctrl)
    router = Router()

    router.message.register(cb.show_menu, Command("start", "menu"))

    router.callback_query.register(cb.cb_back_menu, F.data == "back_menu")
    router.callback_query.register(cb.cb_menu_rooms, F.data == "menu_rooms")
    router.callback_query.register(cb.cb_menu_price, F.data == "menu_price")
    router.callback_query.register(cb.cb_menu_area, F.data == "menu_area")
    router.callback_query.register(cb.cb_menu_status, F.data == "menu_status")
    router.callback_query.register(cb.cb_rooms_preset, F.data.startswith("rooms_"))
    router.callback_query.register(cb.cb_price_preset, F.data.startswith("price_"))
    router.callback_query.register(cb.cb_area_preset, F.data.startswith("area_"))
    router.callback_query.register(cb.cb_status_value, F.data.startswith("status_"))
    router.callback_query.register(cb.cb_show_filter, F.data == "show_filter")
    router.callback_query.register(cb.cb_reset, F.data == "reset_filter")
    router.callback_query.register(cb.cb_pause, F.data == "pause")
    router.callback_query.register(cb.cb_resume, F.data == "resume")
    router.callback_query.register(cb.cb_lang, F.data.startswith("lang_"))

    return router
