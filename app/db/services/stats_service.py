# ============================================================
# services/stats_service.py — Aggregate stats for /stats command
# ============================================================

import logging
from dataclasses import dataclass

from cache import seen_store
from database import db
from repositories.listing import ListingRepository
from schemas.listing import ListingCountResponse, ListingStatsRequest, PriceStatsRow

logger = logging.getLogger(__name__)


@dataclass
class FullStatsResponse:
    """Combined DB + Redis stats returned to bot_commands."""

    total_all_time:    int
    total_today:       int
    redis_seen_count:  int
    redis_local_mirror: int
    redis_memory_mb:   float
    price_rows:        list[PriceStatsRow]


class StatsService:
    """Fetches and combines DB + Redis statistics."""

    def __init__(self) -> None:
        self._repo = ListingRepository()

    async def get_full_stats(self, max_price_rows: int = 12) -> FullStatsResponse:
        async with db.session_context():
            counts: ListingCountResponse = await self._repo.get_counts()
            price_rows: list[PriceStatsRow] = await self._repo.get_price_stats(
                ListingStatsRequest(max_rows=max_price_rows)
            )

        redis_info = await seen_store.stats()

        return FullStatsResponse(
            total_all_time     = counts.total_all_time,
            total_today        = counts.total_today,
            redis_seen_count   = redis_info.get("seen_count", 0),
            redis_local_mirror = redis_info.get("local_mirror", 0),
            redis_memory_mb    = redis_info.get("redis_memory_mb", 0.0),
            price_rows         = price_rows,
        )