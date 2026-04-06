import logging
from datetime import datetime

import asyncio

from app.telegram.notifier import TelegramNotifier
from app.db.repositories.listing_repo import ListingRepository
from app.core.apartment import Apartment, ApartmentFilter, ProcessResult
from app.db.schemas.listing_scm import (
    MarkNotifiedRequest,
    UpsertListingRequest,
    UpsertListingResponse,
)

logger = logging.getLogger(__name__)


def _parse_published_at(value: datetime | str | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        logger.debug("Unable to parse published_at=%s", value)
        return None


class ListingService:
    _locks: dict[tuple[str, str], asyncio.Lock] = {}
    _global_lock = asyncio.Lock()

    def __init__(self):
        self.repo = ListingRepository()
        self._history_cache: dict[str, set[str]] = {}
        self._uid_by_url_cache: dict[str, str | None] = {}
        self._upsert_cache: dict[str, UpsertListingResponse] = {}

    async def _was_sent_to_user(self, apartment_id: str, chat_id: str) -> bool:
        history = self._history_cache.get(chat_id)
        if history is not None:
            return apartment_id in history
        return await self.repo.exists(apartment_id, chat_id)

    async def _normalize_identity(self, apartment: Apartment) -> Apartment:
        if not apartment.url:
            return apartment

        existing_uid = self._uid_by_url_cache.get(apartment.url)
        if existing_uid is None and apartment.url not in self._uid_by_url_cache:
            existing_uid = await self.repo.get_existing_uid_by_url(apartment.url)
            self._uid_by_url_cache[apartment.url] = existing_uid

        if existing_uid and existing_uid != apartment.id:
            apartment.id = existing_uid
        return apartment

    async def _remember_sent_apartment(self, apt_id: str, chat_id: str) -> None:
        history = self._history_cache.get(chat_id)
        if history is not None:
            history.add(apt_id)
        await self.repo.add_log(apt_id, chat_id)

    async def _get_lock(self, apt_id: str, chat_id: str) -> asyncio.Lock:
        key = (apt_id, chat_id)
        async with self._global_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

    async def _get_upsert_response(self, apartment: Apartment) -> UpsertListingResponse:
        cached = self._upsert_cache.get(apartment.id)
        if cached is not None:
            return cached

        response = await self.repo.upsert(self._build_upsert(apartment))
        self._upsert_cache[apartment.id] = response
        if apartment.url:
            self._uid_by_url_cache[apartment.url] = apartment.id
        return response

    async def _send_listing(
        self,
        apartment: Apartment,
        notifier: TelegramNotifier,
        chat_id: str,
        lang: str,
        with_actions: bool,
    ) -> tuple[UpsertListingResponse, bool]:
        upsert_response = await self._get_upsert_response(apartment)
        sent = await notifier.send_apartment(
            int(chat_id),
            apartment,
            listing_id=upsert_response.listing_db_id,
            lang=lang,
            with_actions=with_actions,
        )
        return upsert_response, bool(sent)

    @staticmethod
    def _result(
        apartment_id: str,
        upsert_response: UpsertListingResponse | None,
        passed_filter: bool,
        notified: bool,
    ) -> ProcessResult:
        return ProcessResult(
            apartment_id,
            upsert_response.listing_db_id if upsert_response else None,
            upsert_response.is_new if upsert_response else False,
            passed_filter,
            notified,
        )

    async def preload_user_histories(self, chat_ids: list[str]) -> dict[str, set[str]]:
        missing_chat_ids = [
            chat_id for chat_id in chat_ids if chat_id not in self._history_cache
        ]
        if missing_chat_ids:
            fetched = await self.repo.get_user_notified_uids_map(missing_chat_ids)
            for chat_id in missing_chat_ids:
                self._history_cache[chat_id] = fetched.get(chat_id, set())

        return {
            chat_id: self._history_cache.setdefault(chat_id, set())
            for chat_id in chat_ids
        }

    async def process_apartment(
        self,
        apartment: Apartment,
        apartment_filter: ApartmentFilter,
        chat_id: str,
        notifier: TelegramNotifier,
        lang: str = "en",
        with_actions: bool = False,
        show_special_listings: bool = False,
    ) -> ProcessResult:
        apartment = await self._normalize_identity(apartment)
        lock = await self._get_lock(apartment.id, chat_id)
        lock_key = (apartment.id, chat_id)

        if lock.locked():
            logger.info("Collision: user:%s waiting for apt:%s", chat_id, apartment.id)

        try:
            async with lock:
                if await self._was_sent_to_user(apartment.id, chat_id):
                    return self._result(apartment.id, None, False, False)

                upsert_resp = await self._get_upsert_response(apartment)

                if not apartment.matches(
                    apartment_filter, show_special_listings=show_special_listings
                ):
                    return self._result(apartment.id, upsert_resp, False, False)

                if not upsert_resp.is_new:
                    return self._result(apartment.id, upsert_resp, True, False)

                upsert_resp, sent_message = await self._send_listing(
                    apartment,
                    notifier,
                    chat_id,
                    lang,
                    with_actions,
                )
                if sent_message:
                    await self._remember_sent_apartment(apartment.id, chat_id)
                    try:
                        await self.repo.mark_notified(
                            MarkNotifiedRequest(
                                listing_db_id=upsert_resp.listing_db_id,
                                chat_id=chat_id,
                                uid=apartment.id,
                            )
                        )
                    except Exception as e:
                        logger.debug("Failed to update listing notified flag: %s", e)

                    logger.info(
                        "Success: user:%s notified about apt:%s", chat_id, apartment.id
                    )

                return self._result(apartment.id, upsert_resp, True, sent_message)
        finally:
            async with self._global_lock:
                current_lock = self._locks.get(lock_key)
                if current_lock is lock and not lock.locked():
                    self._locks.pop(lock_key, None)

    async def preview_apartment(
        self,
        apartment: Apartment,
        apartment_filter: ApartmentFilter,
        notifier: TelegramNotifier,
        chat_id: int,
        lang: str = "en",
        with_actions: bool = False,
        show_special_listings: bool = False,
    ) -> bool:
        apartment = await self._normalize_identity(apartment)

        if not apartment.matches(
            apartment_filter, show_special_listings=show_special_listings
        ):
            return False

        _, sent_message = await self._send_listing(
            apartment,
            notifier,
            str(chat_id),
            lang,
            with_actions,
        )
        return sent_message

    async def get_user_history(self, chat_id: str) -> set[str]:
        if chat_id in self._history_cache:
            return self._history_cache[chat_id]
        history = await self.repo.get_user_notified_uids(chat_id)
        self._history_cache[chat_id] = history
        return history

    def _build_upsert(self, apartment: Apartment) -> UpsertListingRequest:
        slug, external_id = apartment.id.split(":", 1)
        return UpsertListingRequest(
            uid=apartment.id,
            source_slug=slug,
            source_name=apartment.source,
            external_id=external_id,
            title=apartment.title,
            url=apartment.url,
            price=apartment.price,
            cold_rent=apartment.cold_rent,
            extra_costs=apartment.extra_costs,
            currency=apartment.currency,
            rooms=apartment.rooms,
            sqm=apartment.sqm,
            floor=apartment.floor,
            address=apartment.address,
            district=apartment.district,
            social_status=apartment.social_status,
            description=apartment.description,
            image_url=apartment.image_url,
            published_at=_parse_published_at(apartment.published_at),
        )

    async def reset_user_history(self, chat_id: str) -> None:
        self._history_cache.pop(chat_id, None)
        await self.repo.delete_user_notification_history(chat_id)

    async def get_listing_by_id(self, listing_id: int):
        return await self.repo.get_by_id(listing_id)
