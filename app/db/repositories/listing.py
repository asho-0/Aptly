# ============================================================
# repositories/listing.py — Listing DB access layer
#
# Rules:
#   • No business logic — only SQL
#   • Accepts schema request objects
#   • Returns schema response objects (never raw ORM rows to callers)
#   • Never imports from services/
# ============================================================

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db_models import Listing, NotificationLog
from repositories.base import BaseRepository
from schemas.listing import (
    ListingCountResponse,
    ListingStatsRequest,
    MarkNotifiedRequest,
    PriceStatsRow,
    UpsertListingRequest,
    UpsertListingResponse,
)

logger = logging.getLogger(__name__)


class ListingRepository(BaseRepository):

    async def upsert(self, req: UpsertListingRequest) -> UpsertListingResponse:
        """
        INSERT … ON CONFLICT (source_slug, external_id) DO UPDATE.
        Returns the DB id and a flag indicating whether the row was newly inserted.
        """
        now  = datetime.now(timezone.utc)
        stmt = (
            pg_insert(Listing)
            .values(
                uid           = req.uid,
                source_slug   = req.source_slug,
                source_name   = req.source_name,
                external_id   = req.external_id,
                title         = req.title,
                url           = req.url,
                price         = req.price,
                currency      = req.currency,
                rooms         = req.rooms,
                sqm           = req.sqm,
                floor         = req.floor,
                address       = req.address,
                district      = req.district,
                social_status = req.social_status,
                description   = req.description,
                image_url     = req.image_url,
                published_at  = req.published_at,
                first_seen_at = now,
                last_seen_at  = now,
            )
            .on_conflict_do_update(
                index_elements = ["source_slug", "external_id"],
                set_           = dict(
                    last_seen_at = now,
                    active       = True,
                    price        = req.price,
                    title        = req.title,
                ),
            )
            .returning(Listing.id, Listing.first_seen_at, Listing.last_seen_at)
        )
        row    = (await self.session.execute(stmt)).one()
        is_new = row.first_seen_at == row.last_seen_at
        return UpsertListingResponse(listing_db_id=row.id, is_new=is_new)

    async def mark_notified(self, req: MarkNotifiedRequest) -> None:
        """
        Mark a listing as notified and append a notification log entry.
        Both writes happen inside the same session — committed together by the caller.
        """
        await self.session.execute(
            update(Listing)
            .where(Listing.id == req.listing_db_id)
            .values(notified=True, notified_at=datetime.now(timezone.utc))
        )
        self.session.add(NotificationLog(
            listing_id = req.listing_db_id,
            chat_id    = req.chat_id,
            success    = req.success,
            error_msg  = req.error_msg,
        ))

    async def get_notified_uids(self) -> list[str]:
        """
        Return all UIDs where notified=True.
        Called once at startup for Redis cache warm-up — not on the hot path.
        """
        rows = (await self.session.execute(
            select(Listing.uid).where(Listing.notified == True)  # noqa: E712
        )).scalars().all()
        return list(rows)

    async def get_counts(self) -> ListingCountResponse:
        total = (await self.session.execute(
            select(func.count()).select_from(Listing)
        )).scalar_one()

        today = (await self.session.execute(
            select(func.count())
            .select_from(Listing)
            .where(func.date(Listing.first_seen_at) == func.current_date())
        )).scalar_one()

        return ListingCountResponse(total_all_time=total, total_today=today)

    async def get_price_stats(self, req: ListingStatsRequest) -> list[PriceStatsRow]:
        where_clauses = ["price IS NOT NULL"]
        if req.only_active:
            where_clauses.append("active = TRUE")
        if req.source_slug:
            where_clauses.append(f"source_slug = '{req.source_slug}'")  # safe — validated by Pydantic
        where = " AND ".join(where_clauses)

        rows = (await self.session.execute(
            text(f"""
                SELECT
                    source_slug,
                    rooms,
                    COUNT(*)                          AS total,
                    ROUND(AVG(price)::numeric, 0)     AS avg_price,
                    MIN(price)                        AS min_price,
                    MAX(price)                        AS max_price
                FROM listings
                WHERE {where}
                GROUP BY source_slug, rooms
                ORDER BY source_slug, rooms
                LIMIT :limit
            """),
            {"limit": req.max_rows},
        )).mappings().all()

        return [
            PriceStatsRow(
                source_slug = r["source_slug"],
                rooms       = r["rooms"],
                total       = r["total"],
                avg_price   = float(r["avg_price"]),
                min_price   = float(r["min_price"]),
                max_price   = float(r["max_price"]),
            )
            for r in rows
        ]