import asyncio
import datetime
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from app.core.enums import SocialStatus
from app.db.models.models import Listing, User
from app.db.schemas.user_scm import UserProfileSchema
from app.db.services import FilterService, ListingService, UserService
from app.db.session import db
from app.parsers.site import InBerlinWohnenScraper
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
    (
        "persons_total",
        ProfileStates.persons_total,
        "text",
        "profile_prompt_persons_total",
    ),
    (
        "wbs_available",
        ProfileStates.wbs_available,
        "choice",
        "profile_prompt_wbs_available",
    ),
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

    async def _iter_scraper_apartments(self, scraper) -> AsyncIterator[Any]:
        if getattr(type(scraper), "iter_listings", None) is not None:
            async for apartment in scraper.iter_listings():
                yield apartment
            return

        for apartment in await scraper.fetch_all():
            yield apartment

    async def _run_preview(self, chat_id: str, store: FilterStore) -> None:
        started_at = time.perf_counter()
        found = 0
        scrapers = [InBerlinWohnenScraper()]
        with_actions = False

        if self.registry.extension_gateway:
            with_actions = await self.registry.extension_gateway.is_connected(chat_id)

        try:
            async with db.session_context():
                if getattr(type(self.listing_svc), "preload_user_histories", None) is not None:
                    await self.listing_svc.preload_user_histories([chat_id])

                for scraper in scrapers:
                    try:
                        async for apartment in self._iter_scraper_apartments(scraper):
                            sent = await self.listing_svc.preview_apartment(
                                apartment,
                                store.current_filter,
                                self.notifier,
                                int(chat_id),
                                lang=store.lang,
                                with_actions=with_actions,
                                show_special_listings=store.show_special_listings,
                            )
                            if sent:
                                found += 1
                    except Exception as exc:
                        logger.error("[%s] preview error: %s", scraper.slug, exc)
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

    @staticmethod
    def _chat_id_from_message(message: Message) -> str:
        return str(message.chat.id)

    async def _get_store(
        self,
        chat_id: str,
        username: str | None = None,
        full_name: str | None = None,
    ) -> FilterStore:
        return await self.ctrl.registry.get_or_create(chat_id, username, full_name)

    async def _get_callback_context(
        self, callback: CallbackQuery
    ) -> tuple[Message, FilterStore]:
        message = _require_message(callback)
        store = await self._get_store(self._chat_id_from_message(message))
        return message, store

    async def _answer_invalid_value(
        self, callback: CallbackQuery, lang: str
    ) -> None:
        await callback.answer(
            self.ctrl.translate("invalid_value", lang=lang), show_alert=True
        )

    async def _open_menu_screen(
        self,
        callback: CallbackQuery,
        text: str,
        reply_markup,
    ) -> None:
        message = _require_message(callback)
        await message.edit_text(text, reply_markup=reply_markup)
        await callback.answer()

    async def _show_choice_screen(
        self,
        callback: CallbackQuery,
        text_key: str,
        reply_markup,
    ) -> None:
        _, store = await self._get_callback_context(callback)
        await self._open_menu_screen(
            callback,
            self.ctrl.translate(text_key, lang=store.lang),
            reply_markup,
        )

    async def _show_filter_menu(
        self,
        callback: CallbackQuery,
        store: FilterStore,
        intro_text: str | None = None,
        lang: str | None = None,
        summary_first: bool = False,
        answer_callback: bool = True,
    ) -> None:
        resolved_lang = lang or store.lang
        summary = store.current_filter.summary(
            resolved_lang, store.show_special_listings
        )
        parts = [part for part in [intro_text, summary] if part]
        if summary_first:
            parts = [part for part in [summary, intro_text] if part]

        message = _require_message(callback)
        await message.edit_text("\n\n".join(parts), reply_markup=main_menu_keyboard())
        if answer_callback:
            await callback.answer()

    async def _answer_alert(
        self, callback: CallbackQuery, text_key: str, lang: str
    ) -> None:
        await callback.answer(self.ctrl.translate(text_key, lang=lang), show_alert=True)

    async def _load_fill_submit_data(
        self, chat_id: str, listing_id: int
    ) -> tuple[User | None, Listing | None]:
        async with db.session_context():
            profile = await self.ctrl.user_svc.get_profile(chat_id)
            listing = await self.ctrl.listing_svc.get_listing_by_id(listing_id)
        return profile, listing

    async def _validate_fill_submit(
        self,
        callback: CallbackQuery,
        store: FilterStore,
        chat_id: str,
        listing: Listing | None,
        serialized_profile: UserProfileSchema,
    ) -> bool:
        if listing is None:
            await self._answer_alert(callback, "listing_missing", store.lang)
            return False

        if not self.ctrl.user_svc.is_profile_complete(serialized_profile):
            await self._answer_alert(callback, "profile_incomplete", store.lang)
            return False

        if not await self.ctrl.extension_gateway.is_connected(chat_id):
            await self._answer_alert(callback, "extension_unavailable", store.lang)
            return False

        return True

    async def _apply_preset_value(
        self,
        callback: CallbackQuery,
        field: str,
        cast_type: type,
    ) -> None:
        message = _require_message(callback)
        _, low, high = str(callback.data).split("_")
        await self._finish_preset(
            callback,
            await self._apply_range(
                self._chat_id_from_message(message), field, low, high, cast_type
            ),
        )

    @staticmethod
    def _profile_save_payload(payload: dict[str, Any]) -> UserProfileSchema:
        return UserProfileSchema(
            salutation=payload["salutation"],
            first_name=payload["first_name"],
            last_name=payload["last_name"],
            email=payload["email"],
            phone=payload["phone"],
            street=payload["street"],
            house_number=payload["house_number"],
            zip_code=payload["zip_code"],
            city=payload["city"],
            persons_total=payload["persons_total"],
            wbs_available=payload["wbs_available"],
            wbs_date=payload["wbs_date"],
            wbs_rooms=payload["wbs_rooms"],
            wbs_income=payload["wbs_income"],
        )

    @staticmethod
    def _profile_prompt_keyboard(field_name: str):
        if field_name == "salutation":
            return profile_salutation_keyboard()
        if field_name == "wbs_available":
            return profile_wbs_available_keyboard()
        if field_name == "wbs_income":
            return profile_income_keyboard()
        return None

    async def _parse_profile_text_value(
        self, field_name: str, text: str, lang: str
    ) -> tuple[bool, Any, str | None]:
        if field_name not in {"persons_total", "wbs_rooms", "wbs_date"}:
            return True, text, None

        if field_name == "wbs_date":
            try:
                datetime.datetime.strptime(text, "%d.%m.%Y")
            except ValueError:
                return False, None, self.ctrl.translate("profile_invalid_date", lang=lang)
            return True, text, None

        if not text.isdigit():
            return False, None, self.ctrl.translate("profile_invalid_number", lang=lang)

        value = int(text)
        if field_name == "persons_total" and value < 1:
            return False, None, self.ctrl.translate("profile_invalid_number", lang=lang)
        if field_name == "wbs_rooms" and not (1 <= value <= 7):
            return False, None, self.ctrl.translate("profile_invalid_number", lang=lang)
        return True, value, None

    async def _handle_profile_choice(
        self,
        callback: CallbackQuery,
        state: FSMContext,
        expected_state: State,
        field_name: str,
        value: Any,
    ) -> None:
        state_name = await state.get_state()
        message, store = await self._get_callback_context(callback)
        if state_name != expected_state.state:
            await self._answer_invalid_value(callback, store.lang)
            return

        await state.update_data(**{field_name: value})
        await callback.answer()
        await self._advance_profile(message, state, store.lang)

    def _profile_summary(self, profile: User | None, lang: str) -> str:
        data = self.ctrl.user_svc.serialize_profile(profile)
        summary = self.ctrl.translate(
            "profile_current",
            lang=lang,
            salutation=data.salutation or "—",
            first_name=data.first_name or "—",
            last_name=data.last_name or "—",
            email=data.email or "—",
            phone=data.phone or "—",
            street=data.street or "—",
            house_number=data.house_number or "—",
            zip_code=data.zip_code or "—",
            city=data.city or "—",
            persons_total=(
                data.persons_total if data.persons_total is not None else "—"
            ),
            wbs_available="Ja" if data.wbs_available else "Nein",
            wbs_date=data.wbs_date or "—",
            wbs_rooms=data.wbs_rooms if data.wbs_rooms is not None else "—",
            wbs_income=data.wbs_income if data.wbs_income is not None else "—",
        )
        return f"{self.ctrl.translate('profile_menu_title', lang=lang)}\n\n{summary}"

    async def _show_profile_menu(
        self, target: Message, lang: str, profile: User | None, edit: bool
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
        await target.answer(
            self.ctrl.translate(prompt_key, lang=lang),
            reply_markup=self._profile_prompt_keyboard(field_name),
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
                    self._profile_save_payload(payload),
                )
            await state.clear()
            if profile is not None:
                await self.ctrl.extension_gateway.push_profile(
                    str(message.chat.id),
                    self.ctrl.user_svc.serialize_profile(profile).model_dump(),
                )
            await message.answer(self.ctrl.translate("profile_saved", lang=lang))
            await self._show_profile_menu(message, lang, profile, edit=False)
            return

        _, next_state, _, _ = PROFILE_FIELDS[next_index]
        await state.set_state(next_state)
        await self._send_profile_prompt(message, next_state.state or "", lang)

    async def _finish_preset(self, callback: CallbackQuery, ok: bool) -> None:
        message, store = await self._get_callback_context(callback)
        if not ok:
            await self._answer_invalid_value(callback, store.lang)
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
            self._chat_id_from_message(message),
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
        message, store = await self._get_callback_context(callback)
        async with db.session_context():
            profile = await self.ctrl.user_svc.get_profile(self._chat_id_from_message(message))
        await state.clear()
        await self._show_profile_menu(message, store.lang, profile, edit=True)
        await callback.answer()

    async def cb_profile_edit(self, callback: CallbackQuery, state: FSMContext) -> None:
        message, store = await self._get_callback_context(callback)
        await state.clear()
        await state.set_state(ProfileStates.salutation)
        await message.answer(self.ctrl.translate("profile_intro", lang=store.lang))
        await self._send_profile_prompt(
            message, ProfileStates.salutation.state or "", store.lang
        )
        await callback.answer()

    async def cb_profile_save(self, callback: CallbackQuery) -> None:
        message, store = await self._get_callback_context(callback)
        async with db.session_context():
            profile = await self.ctrl.user_svc.get_profile(self._chat_id_from_message(message))
        if profile is not None:
            await self.ctrl.extension_gateway.push_profile(
                self._chat_id_from_message(message),
                self.ctrl.user_svc.serialize_profile(profile).model_dump(),
            )
        await callback.answer(
            self.ctrl.translate("profile_synced", lang=store.lang), show_alert=True
        )

    async def handle_profile_text(self, message: Message, state: FSMContext) -> None:
        state_name = await state.get_state()
        if state_name is None:
            return

        store = await self._get_store(self._chat_id_from_message(message))
        text = (message.text or "").strip()
        if not text:
            await message.answer(
                self.ctrl.translate("profile_invalid", lang=store.lang)
            )
            return

        current_field = PROFILE_FIELDS[PROFILE_INDEX[state_name]][0]
        ok, value, error_text = await self._parse_profile_text_value(
            current_field, text, store.lang
        )
        if not ok:
            await message.answer(error_text or "")
            return

        await state.update_data(**{current_field: value})
        await self._advance_profile(message, state, store.lang)

    async def handle_profile_salutation(
        self, callback: CallbackQuery, state: FSMContext
    ) -> None:
        await self._handle_profile_choice(
            callback,
            state,
            ProfileStates.salutation,
            "salutation",
            str(callback.data or "").split(":", 1)[1],
        )

    async def handle_profile_income(
        self, callback: CallbackQuery, state: FSMContext
    ) -> None:
        await self._handle_profile_choice(
            callback,
            state,
            ProfileStates.wbs_income,
            "wbs_income",
            int(str(callback.data or "").split(":", 1)[1]),
        )

    async def handle_profile_wbs_available(
        self, callback: CallbackQuery, state: FSMContext
    ) -> None:
        await self._handle_profile_choice(
            callback,
            state,
            ProfileStates.wbs_available,
            "wbs_available",
            str(callback.data or "").split(":", 1)[1] == "true",
        )

    async def cb_back_menu(self, callback: CallbackQuery) -> None:
        message, store = await self._get_callback_context(callback)
        await self._open_menu_screen(
            callback,
            f"{store.current_filter.summary(store.lang, store.show_special_listings)}\n\n{self.ctrl.translate('menu_title', lang=store.lang)}",
            main_menu_keyboard(),
        )

    async def cb_menu_rooms(self, callback: CallbackQuery) -> None:
        await self._show_choice_screen(callback, "choose_rooms", rooms_keyboard())

    async def cb_menu_price(self, callback: CallbackQuery) -> None:
        await self._show_choice_screen(callback, "choose_price", price_keyboard())

    async def cb_menu_area(self, callback: CallbackQuery) -> None:
        await self._show_choice_screen(callback, "choose_area", area_keyboard())

    async def cb_menu_status(self, callback: CallbackQuery) -> None:
        await self._show_choice_screen(callback, "choose_status", status_keyboard())

    async def cb_menu_special_content(self, callback: CallbackQuery) -> None:
        await self._show_choice_screen(
            callback, "choose_special_content", special_content_keyboard()
        )

    async def cb_rooms_preset(self, callback: CallbackQuery) -> None:
        await self._apply_preset_value(callback, "rooms", int)

    async def cb_price_preset(self, callback: CallbackQuery) -> None:
        await self._apply_preset_value(callback, "price", float)

    async def cb_area_preset(self, callback: CallbackQuery) -> None:
        await self._apply_preset_value(callback, "area", float)

    async def cb_status_value(self, callback: CallbackQuery) -> None:
        message, store = await self._get_callback_context(callback)
        raw = str(callback.data).split("_", 1)[1]
        try:
            status = SocialStatus(raw)
        except ValueError:
            await self._answer_alert(callback, "status_options", store.lang)
            return

        async with db.session_context():
            ok = await self.ctrl.filter_svc.apply_status_update(
                store.current_filter,
                self._chat_id_from_message(message),
                status,
                lang=store.lang,
            )
        await self._finish_preset(callback, ok)

    async def cb_show_filter(self, callback: CallbackQuery) -> None:
        _, store = await self._get_callback_context(callback)
        await self._show_filter_menu(callback, store)

    async def cb_reset(self, callback: CallbackQuery) -> None:
        message, store = await self._get_callback_context(callback)
        store.reset_to_defaults()
        async with db.session_context():
            await self.ctrl.listing_svc.reset_user_history(
                self._chat_id_from_message(message)
            )
        await self._show_filter_menu(
            callback,
            store,
            intro_text=self.ctrl.translate("reset_done", lang=store.lang),
        )

    async def cb_pause(self, callback: CallbackQuery) -> None:
        _, store = await self._get_callback_context(callback)
        store.set_paused(True)
        await self._answer_alert(callback, "paused", store.lang)

    async def cb_resume(self, callback: CallbackQuery) -> None:
        message, store = await self._get_callback_context(callback)
        store.set_paused(False)
        if not store.current_filter.is_complete():
            await self._answer_alert(callback, "filter_incomplete", store.lang)
            return
        self.ctrl.start_preview(self._chat_id_from_message(message), store)
        await self._answer_alert(callback, "resumed", store.lang)

    async def cb_lang(self, callback: CallbackQuery) -> None:
        _, store = await self._get_callback_context(callback)
        new_lang = str(callback.data).split("_", 1)[1]
        store.set_lang(new_lang)
        await self._show_filter_menu(
            callback,
            store,
            intro_text=self.ctrl.translate("menu_title", lang=new_lang),
            lang=new_lang,
            summary_first=True,
            answer_callback=False,
        )
        await self._answer_alert(callback, "lang_changed", new_lang)

    async def cb_special_content(self, callback: CallbackQuery) -> None:
        _, store = await self._get_callback_context(callback)
        enabled = str(callback.data).endswith(":on")
        store.set_show_special_listings(enabled)
        text_key = (
            "special_content_enabled" if enabled else "special_content_disabled"
        )
        await self._show_filter_menu(
            callback,
            store,
            intro_text=self.ctrl.translate(text_key, lang=store.lang),
        )

    async def cb_link_extension(self, callback: CallbackQuery) -> None:
        message, store = await self._get_callback_context(callback)
        pin = await self.ctrl.pairing_store.create_pin(self._chat_id_from_message(message))
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
        message, store = await self._get_callback_context(callback)
        chat_id = self._chat_id_from_message(message)
        listing_id = int(str(callback.data).split(":", 1)[1])
        profile, listing = await self._load_fill_submit_data(chat_id, listing_id)

        serialized_profile = self.ctrl.user_svc.serialize_profile(profile)
        if not await self._validate_fill_submit(
            callback,
            store,
            chat_id,
            listing,
            serialized_profile,
        ):
            return

        await self.ctrl.notifier.edit_listing_status(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=self.ctrl.translate("listing_processing", lang=store.lang),
            is_caption_message=bool(message.photo),
        )

        try:
            await self.ctrl.extension_gateway.dispatch_fill(
                chat_id=chat_id,
                apartment_url=listing.url,
                user_data=serialized_profile.model_dump(),
                message_id=message.message_id,
                is_caption_message=bool(message.photo),
            )
        except RuntimeError:
            await self._answer_alert(callback, "extension_unavailable", store.lang)
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
