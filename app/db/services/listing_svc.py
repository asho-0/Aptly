import logging
from dataclasses import dataclass

import app.seen as seen
from app.telegram.notifier import TelegramNotifier
from app.core.apartment import Apartment, ApartmentFilter
from app.db.repositories.listing_repo import ListingRepository
from app.db.schemas.listing_scm import (
    MarkNotifiedRequest,
    UpsertListingRequest,
    UpsertListingResponse,
)

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    uid: str
    listing_db_id: int | None
    is_new_in_db: bool
    passed_filter: bool
    notified: bool


async def process_apartment(
    apartment: Apartment,
    apartment_filter: ApartmentFilter,
    chat_id: str,
    notifier: TelegramNotifier,
) -> ProcessResult:
    if not seen.is_new(apartment.id):
        return ProcessResult(apartment.id, None, False, False, False)

    repo = ListingRepository()
    upsert_resp: UpsertListingResponse = await repo.upsert(_build_upsert(apartment))

    if not apartment.matches(apartment_filter):
        logger.info(
            "Filtered uid=%s | price=%s rooms=%s sqm=%s | filter: price=%s-%s rooms=%s-%s sqm=%s-%s",
            apartment.id,
            apartment.price,
            apartment.rooms,
            apartment.sqm,
            apartment_filter.min_price,
            apartment_filter.max_price,
            apartment_filter.min_rooms,
            apartment_filter.max_rooms,
            apartment_filter.min_sqm,
            apartment_filter.max_sqm,
        )
        seen.mark_processed(apartment.id)
        return ProcessResult(
            apartment.id, upsert_resp.listing_db_id, upsert_resp.is_new, False, False
        )

    sent = await notifier.send_apartment(int(chat_id), apartment)
    seen.mark_notified(apartment.id)
    await repo.mark_notified(
        MarkNotifiedRequest(listing_db_id=upsert_resp.listing_db_id, chat_id=chat_id)
    )
    logger.info("Notified: uid=%s db_id=%d", apartment.id, upsert_resp.listing_db_id)
    return ProcessResult(
        apartment.id, upsert_resp.listing_db_id, upsert_resp.is_new, True, sent
    )


async def preview_apartment(
    apartment: Apartment,
    apartment_filter: ApartmentFilter,
    notifier: TelegramNotifier,
    chat_id: int,
) -> bool:
    if seen.is_already_notified(apartment.id):
        return False
    if not apartment.matches(apartment_filter):
        return False
    return await notifier.send_apartment(chat_id, apartment)


def _build_upsert(apartment: Apartment) -> UpsertListingRequest:
    slug, external_id = apartment.id.split(":", 1)
    return UpsertListingRequest(
        uid=apartment.id,
        source_slug=slug,
        source_name=apartment.source,
        external_id=external_id,
        title=apartment.title,
        url=apartment.url,
        price=apartment.price,
        currency=apartment.currency,
        rooms=apartment.rooms,
        sqm=apartment.sqm,
        floor=apartment.floor,
        address=apartment.address,
        district=apartment.district,
        social_status=apartment.social_status,
        description=apartment.description,
        image_url=apartment.image_url,
        published_at=apartment.published_at,
    )
