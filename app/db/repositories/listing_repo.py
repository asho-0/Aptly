import typing as t
from datetime import datetime, timezone

from sqlalchemy import delete, select, update, func, cast as sa_cast, Numeric
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import Select

from app.db.models.models import Listing, NotifiedListing
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
                index_elements=[Listing.source_slug, Listing.external_id],
                set_=dict(
                    last_seen_at=datetime.now(timezone.utc),
                    active=True,
                    price=request.price,
                    title=request.title,
                ),
            )
            .returning(Listing.id, Listing.first_seen_at, Listing.last_seen_at)
        )
        
        result = await self.session.execute(stmt)
        row = result.one()
        is_new = row[1] == row[2]

        return UpsertListingResponse(listing_db_id=row[0], is_new=is_new)

    async def get_price_stats(self, max_rows: int = 20) -> list[PriceStatsRow]:
        stmt: Select[t.Any] = (
            select(
                Listing.source_slug,
                Listing.rooms,
                func.count().label("total"),
                func.round(sa_cast(func.avg(Listing.price), Numeric), 0).label("avg_price"),
                func.min(Listing.price).label("min_price"),
                func.max(Listing.price).label("max_price"),
            )
            .where(Listing.price.is_not(None), Listing.active == True)
            .group_by(Listing.source_slug, Listing.rooms)
            .order_by(Listing.source_slug, Listing.rooms)
            .limit(max_rows)
        )
        
        result = await self.session.execute(stmt)
        rows = result.mappings().all()
        
        return [
            PriceStatsRow(
                source_slug=str(row["source_slug"]),
                rooms=row["rooms"],
                total=int(row["total"]),
                avg_price=float(row["avg_price"] or 0),
                min_price=float(row["min_price"] or 0),
                max_price=float(row["max_price"] or 0),
            )
            for row in rows
        ]

    async def exists(self, uid: str, chat_id: str) -> bool:
        query = select(NotifiedListing).where(
            NotifiedListing.uid == uid, 
            NotifiedListing.chat_id == str(chat_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def add_log(self, uid: str, chat_id: str) -> None:
        stmt = pg_insert(NotifiedListing).values(
            uid=uid,
            chat_id=str(chat_id),
            timestamp=datetime.now(timezone.utc)
        ).on_conflict_do_nothing()
        await self.session.execute(stmt)

    async def mark_notified(self, request: MarkNotifiedRequest) -> None:
        await self.session.execute(
            update(Listing)
            .where(Listing.id == request.listing_db_id)
            .values(notified=True, notified_at=datetime.now(timezone.utc))
        )
        
        if hasattr(request, 'uid') and request.uid:
            await self.add_log(uid=request.uid, chat_id=request.chat_id)

    async def get_total_count(self) -> int:
        return (await self.session.execute(select(func.count()).select_from(Listing))).scalar_one()

    async def delete_user_notification_history(self, chat_id: str) -> None:
        stmt = delete(NotifiedListing).where(NotifiedListing.chat_id == str(chat_id))
        await self.session.execute(stmt)

    async def get_user_notified_uids(self, chat_id: str) -> set[str]:
        query = select(NotifiedListing.uid).where(NotifiedListing.chat_id == str(chat_id))
        result = await self.session.execute(query)
        return set(result.scalars().all())