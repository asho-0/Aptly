# ============================================================
# services/cache_service.py — Redis cache warm-up & maintenance
# ============================================================

import logging

from cache import seen_store
from database import db
from repositories.listing import ListingRepository

logger = logging.getLogger(__name__)


class CacheService:
    """Handles Redis cache warm-up from PostgreSQL and periodic cleanup."""

    def __init__(self) -> None:
        self._repo = ListingRepository()

    async def warm_from_db(self) -> dict[str, int]:
        """
        Load all notified UIDs from PostgreSQL and push them to Redis.
        Safe to call on every startup — warm_from_db is a no-op for UIDs
        already present in Redis.

        Returns a summary dict for logging.
        """
        async with db.session_context():
            uids = await self._repo.get_notified_uids()

        added = await seen_store.warm_from_db(uids)
        logger.info(
            "Cache warm-up complete: %d UIDs from DB, %d new entries added to Redis",
            len(uids), added,
        )
        return {"db_uids": len(uids), "redis_added": added}

    async def run_cleanup(self) -> dict[str, int]:
        """Remove stale UIDs from Redis (older than REDIS_SEEN_TTL). Returns summary."""
        removed = await seen_store.cleanup_expired()
        stats   = await seen_store.stats()
        logger.info(
            "Redis cleanup: %d UIDs removed | cache now %d entries | %.1f MB",
            removed,
            stats.get("seen_count", 0),
            stats.get("redis_memory_mb", 0),
        )
        return {"removed": removed, **stats}