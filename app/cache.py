# ============================================================
# cache.py — Redis-backed seen-IDs store
#
# Redis data layout
# ─────────────────
#   Key  : "wohnungsbot:seen"   (a Redis Set)
#   Value: one member per listing UID  →  "{slug}:{external_id}"
#
# Why a Redis Set?
#   • SISMEMBER  O(1)  — instant "have we seen this?" check
#   • SADD        O(1)  — mark a listing as seen
#   • SMEMBERS   O(N)  — bulk-load into memory on startup
#   • Automatic expiry via individual key TTLs on a Hash variant
#     (see _HASH_KEY approach below for per-member TTL support)
#
# Per-member TTL strategy
# ───────────────────────
# Plain Redis Sets don't support per-member TTL.
# We use a Redis Hash  "wohnungsbot:seen_ts"  that stores
#   field  = uid
#   value  = unix timestamp of when it was first seen
# A periodic cleanup task removes entries older than REDIS_SEEN_TTL.
# This keeps memory bounded without touching PostgreSQL.
# ============================================================

import logging
import time
import typing as t

from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError

from config import settings

logger = logging.getLogger(__name__)

_SET_KEY = "wohnungsbot:seen"        # Redis Set  — for fast SISMEMBER
_TS_KEY  = "wohnungsbot:seen_ts"     # Redis Hash — uid → first_seen unix ts


class RedisSeenStore:
    """
    Redis-backed store for already-notified listing UIDs.

    Startup flow
    ────────────
    1. Call `await store.connect()`
    2. Call `await store.warm_from_db(uids)` with UIDs of all DB rows
       where notified=True — this is the ONE-TIME migration from DB.
       On subsequent starts Redis already has them.
    3. Use `is_new()` / `mark_seen()` in the hot path.

    The in-process set `_local` is a write-through cache so we
    never pay a Redis round-trip for listings we already rejected
    this session.
    """

    def __init__(self) -> None:
        self._redis:  Redis | None = None
        self._local:  set[str]     = set()   # write-through in-memory mirror

    # ── Lifecycle ─────────────────────────────────────────────

    async def connect(self) -> None:
        pool = ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections = 10,
            decode_responses = True,
        )
        self._redis = Redis(connection_pool=pool)
        await self._redis.ping()
        logger.info("Redis connected: %s (db=%d)", settings.REDIS_HOST, settings.REDIS_DB)

        # Load existing members into local mirror
        members = await self._redis.smembers(_SET_KEY)
        self._local.update(members)
        logger.info("RedisSeenStore warmed: %d UIDs in cache", len(self._local))

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()
            logger.info("Redis connection closed")

    # ── Warm from PostgreSQL (one-time / on fresh Redis) ──────

    async def warm_from_db(self, uids: t.Iterable[str]) -> int:
        """
        Bulk-insert UIDs from the DB into Redis.
        Called at startup when Redis is cold (e.g. first run or after flush).
        Returns number of new members added.
        """
        uid_list = [u for u in uids if u not in self._local]
        if not uid_list:
            logger.info("warm_from_db: Redis already up-to-date, nothing to add")
            return 0

        now = str(int(time.time()))
        async with self._redis.pipeline(transaction=False) as pipe:
            # Add to the Set (membership check)
            pipe.sadd(_SET_KEY, *uid_list)
            # Record timestamps in the Hash (for TTL-based cleanup)
            ts_mapping = {uid: now for uid in uid_list}
            pipe.hset(_TS_KEY, mapping=ts_mapping)
            await pipe.execute()

        self._local.update(uid_list)
        logger.info("warm_from_db: %d UIDs pushed to Redis", len(uid_list))
        return len(uid_list)

    # ── Hot path ──────────────────────────────────────────────

    def is_new(self, uid: str) -> bool:
        """
        O(1) local set check — no Redis I/O in the hot path.
        The local mirror is kept in sync by mark_seen().
        """
        return uid not in self._local

    async def mark_seen(self, uid: str) -> None:
        """
        Mark uid as seen in both local mirror and Redis atomically.
        Fire-and-forget safe: if Redis is temporarily unavailable,
        the local mirror still protects against same-session duplicates.
        """
        self._local.add(uid)
        try:
            now = int(time.time())
            async with self._redis.pipeline(transaction=True) as pipe:
                pipe.sadd(_SET_KEY, uid)
                pipe.hset(_TS_KEY, uid, str(now))
                await pipe.execute()
        except RedisError as exc:
            logger.warning("Redis mark_seen failed for %s: %s (local cache still updated)", uid, exc)

    async def mark_seen_batch(self, uids: list[str]) -> None:
        """Mark multiple UIDs at once — used after a scrape batch."""
        self._local.update(uids)
        if not uids:
            return
        try:
            now = str(int(time.time()))
            async with self._redis.pipeline(transaction=False) as pipe:
                pipe.sadd(_SET_KEY, *uids)
                pipe.hset(_TS_KEY, mapping={uid: now for uid in uids})
                await pipe.execute()
        except RedisError as exc:
            logger.warning("Redis mark_seen_batch failed: %s", exc)

    # ── Maintenance ───────────────────────────────────────────

    async def cleanup_expired(self) -> int:
        """
        Remove UIDs older than REDIS_SEEN_TTL from Redis (and local mirror).
        Call this periodically — e.g. once per day.
        Returns number of entries removed.
        """
        cutoff    = int(time.time()) - settings.REDIS_SEEN_TTL
        all_ts    = await self._redis.hgetall(_TS_KEY)
        expired   = [uid for uid, ts in all_ts.items() if int(ts) < cutoff]

        if not expired:
            logger.info("cleanup_expired: nothing to remove")
            return 0

        async with self._redis.pipeline(transaction=False) as pipe:
            pipe.srem(_SET_KEY, *expired)
            pipe.hdel(_TS_KEY, *expired)
            await pipe.execute()

        for uid in expired:
            self._local.discard(uid)

        logger.info("cleanup_expired: removed %d stale UIDs (older than %dd)",
                    len(expired), settings.REDIS_SEEN_TTL // 86400)
        return len(expired)

    async def stats(self) -> dict[str, int | t.Any]:
        """Return diagnostic info."""
        try:
            size     = await self._redis.scard(_SET_KEY)
            ts_count = await self._redis.hlen(_TS_KEY)
            info     = await self._redis.info("memory")
            return {
                "seen_count":       size,
                "ts_entries":       ts_count,
                "local_mirror":     len(self._local),
                "redis_memory_mb":  round(info["used_memory"] / 1024 / 1024, 2),
            }
        except RedisError as exc:
            return {"error": str(exc)}

    def __len__(self) -> int:
        return len(self._local)


# ── Module-level singleton ────────────────────────────────────
seen_store = RedisSeenStore()