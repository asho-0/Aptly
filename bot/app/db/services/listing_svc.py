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

    async def _is_already_notified(self, apt_id: str, chat_id: str) -> bool:
        return await self.repo.exists(apt_id, chat_id)

    async def _normalize_apartment_identity(self, apartment: Apartment) -> Apartment:
        if not apartment.url:
            return apartment

        existing_uid = await self.repo.get_existing_uid_by_url(apartment.url)
        if existing_uid and existing_uid != apartment.id:
            apartment.id = existing_uid
        return apartment

    async def _mark_as_seen(self, apt_id: str, chat_id: str) -> None:
        await self.repo.add_log(apt_id, chat_id)

    async def _get_lock(self, apt_id: str, chat_id: str) -> asyncio.Lock:
        key = (apt_id, chat_id)
        async with self._global_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]

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
        apartment = await self._normalize_apartment_identity(apartment)
        lock = await self._get_lock(apartment.id, chat_id)

        if lock.locked():
            logger.info("Collision: user:%s waiting for apt:%s", chat_id, apartment.id)

        async with lock:
            if await self._is_already_notified(apartment.id, chat_id):
                return ProcessResult(apartment.id, None, False, False, False)

            upsert_resp: UpsertListingResponse = await self.repo.upsert(
                self._build_upsert(apartment)
            )

            if not apartment.matches(
                apartment_filter, show_special_listings=show_special_listings
            ):
                return ProcessResult(
                    apartment.id,
                    upsert_resp.listing_db_id,
                    upsert_resp.is_new,
                    False,
                    False,
                )

            if not upsert_resp.is_new:
                return ProcessResult(
                    apartment.id,
                    upsert_resp.listing_db_id,
                    False,
                    True,
                    False,
                )

            sent_message = await notifier.send_apartment(
                int(chat_id),
                apartment,
                listing_id=upsert_resp.listing_db_id,
                lang=lang,
                with_actions=with_actions,
            )
            if sent_message:
                await self._mark_as_seen(apartment.id, chat_id)
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

            async with self._global_lock:
                self._locks.pop((apartment.id, chat_id), None)

            return ProcessResult(
                apartment.id,
                upsert_resp.listing_db_id,
                upsert_resp.is_new,
                True,
                bool(sent_message),
            )

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
        apartment = await self._normalize_apartment_identity(apartment)
        str_chat_id = str(chat_id)

        if not apartment.matches(
            apartment_filter, show_special_listings=show_special_listings
        ):
            return False
        if await self._is_already_notified(apartment.id, str_chat_id):
            return False

        upsert_resp = await self.repo.upsert(self._build_upsert(apartment))

        sent_message = await notifier.send_apartment(
            int(chat_id),
            apartment,
            listing_id=upsert_resp.listing_db_id,
            lang=lang,
            with_actions=with_actions,
        )
        if sent_message:
            await self._mark_as_seen(apartment.id, str_chat_id)
        return bool(sent_message)

    async def get_user_history(self, chat_id: str) -> set[str]:
        return await self.repo.get_user_notified_uids(chat_id)

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
        await self.repo.delete_user_notification_history(chat_id)

    async def get_listing_by_id(self, listing_id: int):
        return await self.repo.get_by_id(listing_id)
