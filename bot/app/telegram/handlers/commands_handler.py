import asyncio
import datetime
import logging
import time
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.core.config import settings
from app.core.enums import SocialStatus
from app.db.services import FilterService, ListingService, UserService
from app.db.session import db
from app.parsers.site import ALL_SCRAPERS
from app.realtime import ExtensionGateway, PairingStore
from app.telegram.handlers import FilterStore, UserRegistry
from app.telegram.interface.keyboards import (
    area_keyboard,
    main_menu_keyboard,
    price_keyboard,
    profile_menu_keyboard,
    profile_income_keyboard,
    profile_salutation_keyboard,
    profile_wbs_available_keyboard,
    rooms_keyboard,
    special_content_keyboard,
    status_keyboard,
)
from app.telegram.interface.labels import TRANSLATIONS
from app.telegram.notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class ProfileStates(StatesGroup):
    salutation = State()
    first_name = State()
    last_name = State()
    email = State()
    phone = State()
    street = State()
    house_number = State()
    zip_code = State()
    city = State()
    persons_total = State()
    wbs_available = State()
    wbs_date = State()
    wbs_rooms = State()
    wbs_income = State()


PROFILE_FIELDS: list[tuple[str, State, str, str]] = [
    ("salutation", ProfileStates.salutation, "choice", "profile_prompt_salutation"),
    ("first_name", ProfileStates.first_name, "text", "profile_prompt_first_name"),
    ("last_name", ProfileStates.last_name, "text", "profile_prompt_last_name"),
    ("email", ProfileStates.email, "text", "profile_prompt_email"),
    ("phone", ProfileStates.phone, "text", "profile_prompt_phone"),
    ("street", ProfileStates.street, "text", "profile_prompt_street"),
    ("house_number", ProfileStates.house_number, "text", "profile_prompt_house_number"),
    ("zip_code", ProfileStates.zip_code, "text", "profile_prompt_zip_code"),
    ("city", ProfileStates.city, "text", "profile_prompt_city"),
    ("persons_total", ProfileStates.persons_total, "text", "profile_prompt_persons_total"),
    ("wbs_available", ProfileStates.wbs_available, "choice", "profile_prompt_wbs_available"),
    ("wbs_date", ProfileStates.wbs_date, "text", "profile_prompt_wbs_date"),
    ("wbs_rooms", ProfileStates.wbs_rooms, "text", "profile_prompt_wbs_rooms"),
    ("wbs_income", ProfileStates.wbs_income, "choice", "profile_prompt_wbs_income"),
]

PROFILE_INDEX = {
    state.state: index for index, (_, state, _, _) in enumerate(PROFILE_FIELDS)
}


def _require_message(callback: CallbackQuery) -> Message:
    if not isinstance(callback.message, Message):
        raise ValueError("No accessible message in callback")
    return callback.message


class BotController:
    def __init__(
        self,
        registry: UserRegistry,
        notifier: TelegramNotifier,
        extension_gateway: ExtensionGateway,
        pairing_store: PairingStore,
    ):
        self.registry = registry
        self.notifier = notifier
        self.extension_gateway = extension_gateway
        self.pairing_store = pairing_store
        self.listing_svc = ListingService()
        self.filter_svc = FilterService()
        self.user_svc = UserService()
        self._preview_tasks: dict[str, asyncio.Task[None]] = {}

    def translate(self, key: str, lang: str | None = None, **kwargs: Any) -> str:
        resolved = lang or "en"
        text = TRANSLATIONS.get(resolved, TRANSLATIONS["en"]).get(key) or TRANSLATIONS[
            "en"
        ].get(key, key)
        return text.format(**kwargs) if kwargs else text

    def start_preview(self, chat_id: str, store: FilterStore) -> None:
        current = self._preview_tasks.get(chat_id)
        if current and not current.done():
            current.cancel()
        task = asyncio.create_task(self._run_preview(chat_id, store))
        self._preview_tasks[chat_id] = task
        task.add_done_callback(lambda _: self._preview_tasks.pop(chat_id, None))

    async def _run_preview(self, chat_id: str, store: FilterStore) -> None:
        started_at = time.perf_counter()
        found = 0
        scrapers = [cls() for cls in ALL_SCRAPERS]

        try:
            results = await asyncio.gather(
                *[scraper.fetch_all() for scraper in scrapers], return_exceptions=True
            )
            for scraper, result in zip(scrapers, results):
                if isinstance(result, BaseException):
                    logger.error("[%s] preview error: %s", scraper.slug, result)
                    continue

                apartments = result
                if not apartments:
                    continue

                async with db.session_context():
                    for apartment in apartments:
                        sent = await self.listing_svc.preview_apartment(
                            apartment,
                            store.current_filter,
                            self.notifier,
                            int(chat_id),
                            lang=store.lang,
                            with_actions=bool(
                                self.registry.extension_gateway
                                and await self.registry.extension_gateway.is_connected(
                                    chat_id
                                )
                            ),
                            show_special_listings=store.show_special_listings,
                        )
                        if sent:
                            found += 1
                            await asyncio.sleep(settings.NOTIFICATION_DELAY)
        finally:
            for scraper in scrapers:
                await scraper.close_session()

        if found == 0:
            await self.notifier.send_text(
                int(chat_id), self.translate("preview_none", lang=store.lang)
            )

        logger.info(
            "Preview for %s completed in %.2fs with %s matches",
            chat_id,
            time.perf_counter() - started_at,
            found,
        )


class CallbackHandlers:
    def __init__(self, controller: BotController):
        self.ctrl = controller

    async def _get_store(
        self,
        chat_id: str,
        username: str | None = None,
        full_name: str | None = None,
    ) -> FilterStore:
        return await self.ctrl.registry.get_or_create(chat_id, username, full_name)

    def _profile_summary(self, profile: Any, lang: str) -> str:
        data = self.ctrl.user_svc.serialize_profile(profile)
        summary = self.ctrl.translate(
            "profile_current",
            lang=lang,
            salutation=data["salutation"] or "—",
            first_name=data["first_name"] or "—",
            last_name=data["last_name"] or "—",
            email=data["email"] or "—",
            phone=data["phone"] or "—",
            street=data["street"] or "—",
            house_number=data["house_number"] or "—",
            zip_code=data["zip_code"] or "—",
            city=data["city"] or "—",
            persons_total=data["persons_total"] if data["persons_total"] is not None else "—",
            wbs_available="Ja" if data["wbs_available"] else "Nein",
            wbs_date=data["wbs_date"] or "—",
            wbs_rooms=data["wbs_rooms"] if data["wbs_rooms"] is not None else "—",
            wbs_income=data["wbs_income"] if data["wbs_income"] is not None else "—",
        )
        return f"{self.ctrl.translate('profile_menu_title', lang=lang)}\n\n{summary}"

    async def _show_profile_menu(
        self, target: Message, lang: str, profile: Any, edit: bool
    ) -> None:
        text = self._profile_summary(profile, lang)
        if edit:
            await target.edit_text(text, reply_markup=profile_menu_keyboard())
            return
        await target.answer(text, reply_markup=profile_menu_keyboard())

    async def _send_profile_prompt(
        self, target: Message, state_name: str, lang: str
    ) -> None:
        field_name, _, _, prompt_key = PROFILE_FIELDS[PROFILE_INDEX[state_name]]
        reply_markup = None
        if field_name == "salutation":
            reply_markup = profile_salutation_keyboard()
        elif field_name == "wbs_available":
            reply_markup = profile_wbs_available_keyboard()
        elif field_name == "wbs_income":
            reply_markup = profile_income_keyboard()
        await target.answer(
            self.ctrl.translate(prompt_key, lang=lang), reply_markup=reply_markup
        )

    async def _advance_profile(
        self, message: Message, state: FSMContext, lang: str
    ) -> None:
        current_state = await state.get_state()
        if current_state is None:
            return

        current_index = PROFILE_INDEX[current_state]
        next_index = current_index + 1
        if next_index >= len(PROFILE_FIELDS):
            payload = await state.get_data()
            async with db.session_context():
                profile = await self.ctrl.user_svc.save_profile(
                    str(message.chat.id),
                    {
                        "salutation": payload["salutation"],
                        "first_name": payload["first_name"],
                        "last_name": payload["last_name"],
                        "email": payload["email"],
                        "phone": payload["phone"],
                        "street": payload["street"],
                        "house_number": payload["house_number"],
                        "zip_code": payload["zip_code"],
                        "city": payload["city"],
                        "persons_total": payload["persons_total"],
                        "wbs_available": payload["wbs_available"],
                        "wbs_date": payload["wbs_date"],
                        "wbs_rooms": payload["wbs_rooms"],
                        "wbs_income": payload["wbs_income"],
                    },
                )
            await state.clear()
            if profile is not None:
                await self.ctrl.extension_gateway.push_profile(
                    str(message.chat.id),
                    self.ctrl.user_svc.serialize_profile(profile),
                )
            await message.answer(self.ctrl.translate("profile_saved", lang=lang))
            await self._show_profile_menu(message, lang, profile, edit=False)
            return

        _, next_state, _, _ = PROFILE_FIELDS[next_index]
        await state.set_state(next_state)
        await self._send_profile_prompt(message, next_state.state or "", lang)

    async def _finish_preset(self, callback: CallbackQuery, ok: bool) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        if not ok:
            await callback.answer(
                self.ctrl.translate("invalid_value", lang=store.lang), show_alert=True
            )
            return

        summary = store.current_filter.summary(store.lang, store.show_special_listings)
        await message.edit_text(
            f"{self.ctrl.translate('filter_updated', lang=store.lang)}\n\n{summary}",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()
        if not store.is_paused and store.current_filter.is_complete():
            await message.answer(
                self.ctrl.translate("preview_searching", lang=store.lang)
            )
            self.ctrl.start_preview(str(message.chat.id), store)

    async def _apply_range(
        self, chat_id: str, field: str, low: str, high: str, cast_type: type
    ) -> bool:
        store = await self._get_store(chat_id)
        async with db.session_context():
            return await self.ctrl.filter_svc.apply_range_update(
                store.current_filter,
                chat_id,
                field,
                [low, high],
                cast_type,
                lang=store.lang,
            )

    async def show_menu(self, message: Message) -> None:
        user = message.from_user
        store = await self._get_store(
            str(message.chat.id),
            getattr(user, "username", None),
            getattr(user, "full_name", None),
        )
        summary = store.current_filter.summary(store.lang, store.show_special_listings)
        sent = await message.answer(
            f"{summary}\n\n{self.ctrl.translate('menu_title', lang=store.lang)}",
            reply_markup=main_menu_keyboard(),
        )
        if message.bot:
            await message.bot.pin_chat_message(
                chat_id=message.chat.id,
                message_id=sent.message_id,
                disable_notification=True,
            )

    async def start_profile(self, callback: CallbackQuery, state: FSMContext) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        async with db.session_context():
            profile = await self.ctrl.user_svc.get_profile(str(message.chat.id))
        await state.clear()
        await self._show_profile_menu(message, store.lang, profile, edit=True)
        await callback.answer()

    async def cb_profile_edit(self, callback: CallbackQuery, state: FSMContext) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        await state.clear()
        await state.set_state(ProfileStates.salutation)
        await message.answer(self.ctrl.translate("profile_intro", lang=store.lang))
        await self._send_profile_prompt(
            message, ProfileStates.salutation.state or "", store.lang
        )
        await callback.answer()

    async def cb_profile_save(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        async with db.session_context():
            profile = await self.ctrl.user_svc.get_profile(str(message.chat.id))
        if profile is not None:
            await self.ctrl.extension_gateway.push_profile(
                str(message.chat.id),
                self.ctrl.user_svc.serialize_profile(profile),
            )
        await callback.answer(
            self.ctrl.translate("profile_synced", lang=store.lang), show_alert=True
        )

    async def handle_profile_text(self, message: Message, state: FSMContext) -> None:
        state_name = await state.get_state()
        if state_name is None:
            return

        store = await self._get_store(str(message.chat.id))
        text = (message.text or "").strip()
        if not text:
            await message.answer(
                self.ctrl.translate("profile_invalid", lang=store.lang)
            )
            return

        current_field = PROFILE_FIELDS[PROFILE_INDEX[state_name]][0]
        value: Any = text
        if current_field in {"persons_total", "wbs_rooms"}:
            if not text.isdigit():
                await message.answer(
                    self.ctrl.translate("profile_invalid_number", lang=store.lang)
                )
                return
            value = int(text)
            if current_field == "persons_total" and value < 1:
                await message.answer(
                    self.ctrl.translate("profile_invalid_number", lang=store.lang)
                )
                return
            if current_field == "wbs_rooms" and (value < 1 or value > 7):
                await message.answer(
                    self.ctrl.translate("profile_invalid_number", lang=store.lang)
                )
                return
        elif current_field == "wbs_date":
            try:
                value = datetime.date.fromisoformat(text)
            except ValueError:
                await message.answer(
                    self.ctrl.translate("profile_invalid_date", lang=store.lang)
                )
                return

        await state.update_data(**{current_field: value})
        await self._advance_profile(message, state, store.lang)

    async def handle_profile_salutation(
        self, callback: CallbackQuery, state: FSMContext
    ) -> None:
        state_name = await state.get_state()
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        if state_name != ProfileStates.salutation.state:
            await callback.answer(
                self.ctrl.translate("invalid_value", lang=store.lang), show_alert=True
            )
            return
        value = str(callback.data or "").split(":", 1)[1]
        await state.update_data(salutation=value)
        await callback.answer()
        await self._advance_profile(message, state, store.lang)

    async def handle_profile_income(
        self, callback: CallbackQuery, state: FSMContext
    ) -> None:
        state_name = await state.get_state()
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        if state_name != ProfileStates.wbs_income.state:
            await callback.answer(
                self.ctrl.translate("invalid_value", lang=store.lang), show_alert=True
            )
            return
        value = int(str(callback.data or "").split(":", 1)[1])
        await state.update_data(wbs_income=value)
        await callback.answer()
        await self._advance_profile(message, state, store.lang)

    async def handle_profile_wbs_available(
        self, callback: CallbackQuery, state: FSMContext
    ) -> None:
        state_name = await state.get_state()
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        if state_name != ProfileStates.wbs_available.state:
            await callback.answer(
                self.ctrl.translate("invalid_value", lang=store.lang), show_alert=True
            )
            return
        value = str(callback.data or "").split(":", 1)[1] == "true"
        await state.update_data(wbs_available=value)
        await callback.answer()
        await self._advance_profile(message, state, store.lang)

    async def cb_back_menu(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        await message.edit_text(
            f"{store.current_filter.summary(store.lang, store.show_special_listings)}\n\n{self.ctrl.translate('menu_title', lang=store.lang)}",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()

    async def cb_menu_rooms(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        await message.edit_text(
            self.ctrl.translate("choose_rooms", lang=store.lang),
            reply_markup=rooms_keyboard(),
        )
        await callback.answer()

    async def cb_menu_price(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        await message.edit_text(
            self.ctrl.translate("choose_price", lang=store.lang),
            reply_markup=price_keyboard(),
        )
        await callback.answer()

    async def cb_menu_area(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        await message.edit_text(
            self.ctrl.translate("choose_area", lang=store.lang),
            reply_markup=area_keyboard(),
        )
        await callback.answer()

    async def cb_menu_status(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        await message.edit_text(
            self.ctrl.translate("choose_status", lang=store.lang),
            reply_markup=status_keyboard(),
        )
        await callback.answer()

    async def cb_menu_special_content(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        await message.edit_text(
            self.ctrl.translate("choose_special_content", lang=store.lang),
            reply_markup=special_content_keyboard(),
        )
        await callback.answer()

    async def cb_rooms_preset(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        _, low, high = str(callback.data).split("_")
        await self._finish_preset(
            callback,
            await self._apply_range(str(message.chat.id), "rooms", low, high, int),
        )

    async def cb_price_preset(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        _, low, high = str(callback.data).split("_")
        await self._finish_preset(
            callback,
            await self._apply_range(str(message.chat.id), "price", low, high, float),
        )

    async def cb_area_preset(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        _, low, high = str(callback.data).split("_")
        await self._finish_preset(
            callback,
            await self._apply_range(str(message.chat.id), "area", low, high, float),
        )

    async def cb_status_value(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        raw = str(callback.data).split("_", 1)[1]
        try:
            status = SocialStatus(raw)
        except ValueError:
            await callback.answer(
                self.ctrl.translate("status_options", lang=store.lang), show_alert=True
            )
            return

        async with db.session_context():
            ok = await self.ctrl.filter_svc.apply_status_update(
                store.current_filter,
                str(message.chat.id),
                status,
                lang=store.lang,
            )
        await self._finish_preset(callback, ok)

    async def cb_show_filter(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        await message.edit_text(
            store.current_filter.summary(store.lang, store.show_special_listings),
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()

    async def cb_reset(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        store.reset_to_defaults()
        async with db.session_context():
            await self.ctrl.listing_svc.reset_user_history(str(message.chat.id))
        await message.edit_text(
            f"{self.ctrl.translate('reset_done', lang=store.lang)}\n\n{store.current_filter.summary(store.lang, store.show_special_listings)}",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()

    async def cb_pause(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        store.set_paused(True)
        await callback.answer(
            self.ctrl.translate("paused", lang=store.lang), show_alert=True
        )

    async def cb_resume(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        store.set_paused(False)
        if not store.current_filter.is_complete():
            await callback.answer(
                self.ctrl.translate("filter_incomplete", lang=store.lang),
                show_alert=True,
            )
            return
        self.ctrl.start_preview(str(message.chat.id), store)
        await callback.answer(
            self.ctrl.translate("resumed", lang=store.lang), show_alert=True
        )

    async def cb_lang(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        new_lang = str(callback.data).split("_", 1)[1]
        store = await self._get_store(str(message.chat.id))
        store.set_lang(new_lang)
        await message.edit_text(
            f"{store.current_filter.summary(new_lang, store.show_special_listings)}\n\n{self.ctrl.translate('menu_title', lang=new_lang)}",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer(
            self.ctrl.translate("lang_changed", lang=new_lang), show_alert=True
        )

    async def cb_special_content(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        enabled = str(callback.data).endswith(":on")
        store.set_show_special_listings(enabled)
        await message.edit_text(
            f"{self.ctrl.translate('special_content_enabled' if enabled else 'special_content_disabled', lang=store.lang)}\n\n"
            f"{store.current_filter.summary(store.lang, store.show_special_listings)}",
            reply_markup=main_menu_keyboard(),
        )
        await callback.answer()

    async def cb_link_extension(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        pin = await self.ctrl.pairing_store.create_pin(str(message.chat.id))
        await message.answer(
            self.ctrl.translate("pairing_pin", lang=store.lang, pin=pin),
            parse_mode="HTML",
        )
        await callback.answer()

    async def cb_skip_fill(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        await self.ctrl.notifier.clear_listing_actions(
            message.chat.id, message.message_id
        )
        await callback.answer()

    async def cb_fill_submit(self, callback: CallbackQuery) -> None:
        message = _require_message(callback)
        store = await self._get_store(str(message.chat.id))
        listing_id = int(str(callback.data).split(":", 1)[1])

        async with db.session_context():
            profile = await self.ctrl.user_svc.get_profile(str(message.chat.id))
            listing = await self.ctrl.listing_svc.get_listing_by_id(listing_id)

        serialized_profile = self.ctrl.user_svc.serialize_profile(profile)
        if listing is None:
            await callback.answer(
                self.ctrl.translate("listing_missing", lang=store.lang), show_alert=True
            )
            return

        if not self.ctrl.user_svc.is_profile_complete(serialized_profile):
            await callback.answer(
                self.ctrl.translate("profile_incomplete", lang=store.lang),
                show_alert=True,
            )
            return

        if not await self.ctrl.extension_gateway.is_connected(str(message.chat.id)):
            await callback.answer(
                self.ctrl.translate("extension_unavailable", lang=store.lang),
                show_alert=True,
            )
            return

        await self.ctrl.notifier.edit_listing_status(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=self.ctrl.translate("listing_processing", lang=store.lang),
            is_caption_message=bool(message.photo),
        )

        try:
            await self.ctrl.extension_gateway.dispatch_fill(
                chat_id=str(message.chat.id),
                apartment_url=listing.url,
                user_data=serialized_profile,
                message_id=message.message_id,
                is_caption_message=bool(message.photo),
            )
        except RuntimeError:
            await callback.answer(
                self.ctrl.translate("extension_unavailable", lang=store.lang),
                show_alert=True,
            )
            return

        await callback.answer()


def setup_router(
    registry: UserRegistry,
    notifier: TelegramNotifier,
    extension_gateway: ExtensionGateway,
    pairing_store: PairingStore,
) -> Router:
    controller = BotController(registry, notifier, extension_gateway, pairing_store)
    callbacks = CallbackHandlers(controller)
    router = Router()

    router.message.register(callbacks.show_menu, Command("start", "menu"))
    router.message.register(
        callbacks.handle_profile_text, StateFilter(ProfileStates.email)
    )
    router.message.register(
        callbacks.handle_profile_text, StateFilter(ProfileStates.phone)
    )
    router.message.register(
        callbacks.handle_profile_text, StateFilter(ProfileStates.street)
    )
    router.message.register(
        callbacks.handle_profile_text, StateFilter(ProfileStates.house_number)
    )
    router.message.register(
        callbacks.handle_profile_text, StateFilter(ProfileStates.zip_code)
    )
    router.message.register(
        callbacks.handle_profile_text, StateFilter(ProfileStates.city)
    )
    router.message.register(
        callbacks.handle_profile_text, StateFilter(ProfileStates.persons_total)
    )
    router.message.register(
        callbacks.handle_profile_text, StateFilter(ProfileStates.wbs_date)
    )
    router.message.register(
        callbacks.handle_profile_text, StateFilter(ProfileStates.wbs_rooms)
    )
    router.message.register(
        callbacks.handle_profile_text, StateFilter(ProfileStates.first_name)
    )
    router.message.register(
        callbacks.handle_profile_text, StateFilter(ProfileStates.last_name)
    )

    router.callback_query.register(callbacks.cb_back_menu, F.data == "back_menu")
    router.callback_query.register(callbacks.cb_menu_rooms, F.data == "menu_rooms")
    router.callback_query.register(callbacks.cb_menu_price, F.data == "menu_price")
    router.callback_query.register(callbacks.cb_menu_area, F.data == "menu_area")
    router.callback_query.register(callbacks.cb_menu_status, F.data == "menu_status")
    router.callback_query.register(
        callbacks.cb_menu_special_content, F.data == "menu_special_content"
    )
    router.callback_query.register(
        callbacks.cb_rooms_preset, F.data.startswith("rooms_")
    )
    router.callback_query.register(
        callbacks.cb_price_preset, F.data.startswith("price_")
    )
    router.callback_query.register(callbacks.cb_area_preset, F.data.startswith("area_"))
    router.callback_query.register(
        callbacks.cb_status_value, F.data.startswith("status_")
    )
    router.callback_query.register(callbacks.cb_show_filter, F.data == "show_filter")
    router.callback_query.register(callbacks.cb_reset, F.data == "reset_filter")
    router.callback_query.register(callbacks.cb_pause, F.data == "pause")
    router.callback_query.register(callbacks.cb_resume, F.data == "resume")
    router.callback_query.register(callbacks.cb_lang, F.data.startswith("lang_"))
    router.callback_query.register(
        callbacks.cb_special_content, F.data.startswith("special_content:")
    )
    router.callback_query.register(callbacks.start_profile, F.data == "profile_start")
    router.callback_query.register(callbacks.cb_profile_edit, F.data == "profile_edit")
    router.callback_query.register(callbacks.cb_profile_save, F.data == "profile_save")
    router.callback_query.register(
        callbacks.cb_link_extension, F.data == "link_extension"
    )
    router.callback_query.register(
        callbacks.handle_profile_salutation, F.data.startswith("profile_salutation:")
    )
    router.callback_query.register(
        callbacks.handle_profile_income, F.data.startswith("profile_income:")
    )
    router.callback_query.register(
        callbacks.handle_profile_wbs_available,
        F.data.startswith("profile_wbs_available:"),
    )
    router.callback_query.register(
        callbacks.cb_skip_fill, F.data.startswith("skip_fill:")
    )
    router.callback_query.register(
        callbacks.cb_fill_submit, F.data.startswith("fill_submit:")
    )

    return router
