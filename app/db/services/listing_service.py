# ============================================================
# services/listing_service.py — Listing business logic
#
# Sits between main.py (caller) and ListingRepository (DB).
# Responsible for:
#   • Building the correct request objects from domain models
#   • Deciding whether to notify (filter matching)
#   • Coordinating the upsert → notify → Redis write sequence
#   • Returning typed results — never raw DB rows
# ============================================================

import logging
from dataclasses import dataclass

from app_models import Apartment, ApartmentFilter
from cache import seen_store
from database import db
from repositories.listing import ListingRepository
from schemas.listing import (
    MarkNotifiedRequest,
    UpsertListingRequest,
    UpsertListingResponse,
)

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    """Outcome of processing one apartment through the pipeline."""

    uid:           str
    listing_db_id: int
    is_new_in_db:  bool
    passed_filter: bool
    notified:      bool


class ListingService:
    """
    Orchestrates the full lifecycle of a scraped listing:
        scraper → upsert → filter check → notify → mark notified
    """

    def __init__(self) -> None:
        self._repo = ListingRepository()

    async def process(
        self,
        apt:         Apartment,
        filt:        ApartmentFilter,
        chat_id:     str,
        notifier,    # TelegramNotifier — injected to avoid circular import
    ) -> ProcessResult:
        """
        Process a single apartment inside an active session_context().
        Returns a ProcessResult describing what happened.
        """
        # ── Step 1: always persist to DB regardless of filter ─
        upsert_req = self._build_upsert_request(apt)
        upsert_res: UpsertListingResponse = await self._repo.upsert(upsert_req)

        # ── Step 2: Redis O(1) dedup check ────────────────────
        if not seen_store.is_new(apt.id):
            return ProcessResult(
                uid           = apt.id,
                listing_db_id = upsert_res.listing_db_id,
                is_new_in_db  = upsert_res.is_new,
                passed_filter = False,
                notified      = False,
            )

        # ── Step 3: apply user's filter ───────────────────────
        if not apt.matches(filt):
            await seen_store.mark_seen(apt.id)   # avoid re-checking next cycle
            return ProcessResult(
                uid           = apt.id,
                listing_db_id = upsert_res.listing_db_id,
                is_new_in_db  = upsert_res.is_new,
                passed_filter = False,
                notified      = False,
            )

        # ── Step 4: send Telegram notification ───────────────
        ok = await notifier.send_apartment(apt)

        # ── Step 5: persist seen state ────────────────────────
        await seen_store.mark_seen(apt.id)
        await self._repo.mark_notified(MarkNotifiedRequest(
            listing_db_id = upsert_res.listing_db_id,
            chat_id       = chat_id,
            success       = ok,
            error_msg     = None if ok else "Telegram send failed",
        ))

        logger.info(
            "Listing processed: uid=%s notified=%s db_id=%d new_in_db=%s",
            apt.id, ok, upsert_res.listing_db_id, upsert_res.is_new,
        )
        return ProcessResult(
            uid           = apt.id,
            listing_db_id = upsert_res.listing_db_id,
            is_new_in_db  = upsert_res.is_new,
            passed_filter = True,
            notified      = ok,
        )

    @staticmethod
    def _build_upsert_request(apt: Apartment) -> UpsertListingRequest:
        """Map domain Apartment → validated UpsertListingRequest."""
        slug, ext = apt.id.split(":", 1)
        return UpsertListingRequest(
            uid           = apt.id,
            source_slug   = slug,
            source_name   = apt.source,
            external_id   = ext,
            title         = apt.title,
            url           = apt.url,
            price         = apt.price,
            currency      = apt.currency,
            rooms         = apt.rooms,
            sqm           = apt.sqm,
            floor         = apt.floor,
            address       = apt.address,
            district      = apt.district,
            social_status = apt.social_status,
            description   = apt.description,
            image_url     = apt.image_url,
            published_at  = apt.published_at,
        )