# ============================================================
# repositories/filter.py — Filter DB access layer
# ============================================================

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db_models import Filter
from repositories.base import BaseRepository
from schemas.filter import FilterResponse, LoadFilterRequest, SaveFilterRequest


class FilterRepository(BaseRepository):

    async def load(self, req: LoadFilterRequest) -> Optional[FilterResponse]:
        row = (await self.session.execute(
            select(Filter).where(Filter.chat_id == req.chat_id)
        )).scalar_one_or_none()

        if not row:
            return None

        return FilterResponse(
            min_rooms        = row.min_rooms,
            max_rooms        = row.max_rooms,
            min_sqm          = float(row.min_sqm)   if row.min_sqm   else None,
            max_sqm          = float(row.max_sqm)   if row.max_sqm   else None,
            min_price        = float(row.min_price) if row.min_price else None,
            max_price        = float(row.max_price) if row.max_price else None,
            social_status    = row.social_status,
            include_keywords = list(row.include_keywords or []),
            exclude_keywords = list(row.exclude_keywords or []),
            paused           = row.paused,
        )

    async def save(self, req: SaveFilterRequest) -> None:
        stmt = (
            pg_insert(Filter)
            .values(
                chat_id          = req.chat_id,
                min_rooms        = req.min_rooms,
                max_rooms        = req.max_rooms,
                min_sqm          = req.min_sqm,
                max_sqm          = req.max_sqm,
                min_price        = req.min_price,
                max_price        = req.max_price,
                social_status    = req.social_status,
                include_keywords = req.include_keywords,
                exclude_keywords = req.exclude_keywords,
                paused           = req.paused,
                updated_at       = datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                index_elements = ["chat_id"],
                set_           = dict(
                    min_rooms        = req.min_rooms,
                    max_rooms        = req.max_rooms,
                    min_sqm          = req.min_sqm,
                    max_sqm          = req.max_sqm,
                    min_price        = req.min_price,
                    max_price        = req.max_price,
                    social_status    = req.social_status,
                    include_keywords = req.include_keywords,
                    exclude_keywords = req.exclude_keywords,
                    paused           = req.paused,
                    updated_at       = datetime.now(timezone.utc),
                ),
            )
        )
        await self.session.execute(stmt)