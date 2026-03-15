from datetime import datetime, timezone

from sqlalchemy import select, update, func, cast, Numeric
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models.models import Listing
from app.db.repositories.base_repo import BaseRepository
from app.db.schemas.listing_scm import (
    MarkNotifiedRequest,
    PriceStatsRow,
    UpsertListingRequest,
    UpsertListingResponse,
)


class ListingRepository(BaseRepository):
    async def upsert(self, request: UpsertListingRequest) -> UpsertListingResponse:
        slug, external_id = request.uid.split(":", 1)
        stmt = (
            pg_insert(Listing)
            .values(
                uid=request.uid,
                source_slug=slug,
                source_name=request.source_name,
                external_id=external_id,
                title=request.title,
                url=request.url,
                price=request.price,
                currency=request.currency,
                rooms=request.rooms,
                sqm=request.sqm,
                floor=request.floor,
                address=request.address,
                district=request.district,
                social_status=request.social_status,
                description=request.description,
                image_url=request.image_url,
                published_at=request.published_at,
                first_seen_at=datetime.now(timezone.utc),
                last_seen_at=datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                index_elements=["source_slug", "external_id"],
                set_=dict(
                    last_seen_at=datetime.now(timezone.utc),
                    active=True,
                    price=request.price,
                    title=request.title,
                ),
            )
            .returning(Listing.id, Listing.first_seen_at, Listing.last_seen_at)
        )
        row = (await self.session.execute(stmt)).one()
        is_new = row.first_seen_at == row.last_seen_at

        return UpsertListingResponse(listing_db_id=row.id, is_new=is_new)

    async def mark_notified(self, request: MarkNotifiedRequest) -> None:
        await self.session.execute(
            update(Listing)
            .where(Listing.id == request.listing_db_id)
            .values(notified=True, notified_at=datetime.now(timezone.utc))
        )

    async def get_notified_uids(self) -> list[str]:
        rows = (
            (
                await self.session.execute(
                    select(Listing.uid).where(Listing.notified == True)
                )
            )
            .scalars()
            .all()
        )
        return list(rows)

    async def get_total_count(self) -> int:
        return (
            await self.session.execute(select(func.count()).select_from(Listing))
        ).scalar_one()

    async def get_count_today(self) -> int:
        return (
            await self.session.execute(
                select(func.count())
                .select_from(Listing)
                .where(func.date(Listing.first_seen_at) == func.current_date())
            )
        ).scalar_one()

    async def get_price_stats(self, max_rows: int = 20) -> list[PriceStatsRow]:
        stmt = (
            select(
                Listing.source_slug,
                Listing.rooms,
                func.count().label("total"),
                func.round(cast(func.avg(Listing.price), Numeric), 0).label(
                    "avg_price"
                ),
                func.min(Listing.price).label("min_price"),
                func.max(Listing.price).label("max_price"),
            )
            .where(Listing.price.is_not(None), Listing.active == True)
            .group_by(Listing.source_slug, Listing.rooms)
            .order_by(Listing.source_slug, Listing.rooms)
            .limit(max_rows)
        )
        rows = (await self.session.execute(stmt)).mappings().all()
        return [
            PriceStatsRow(
                source_slug=row["source_slug"],
                rooms=row["rooms"],
                total=row["total"],
                avg_price=float(row["avg_price"] or 0),
                min_price=float(row["min_price"] or 0),
                max_price=float(row["max_price"] or 0),
            )
            for row in rows
        ]
