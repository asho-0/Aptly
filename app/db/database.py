# ============================================================
# database.py — SQLAlchemy async engine + contextvars sessions
# ============================================================

import logging
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import AsyncGenerator, Optional

from sqlalchemy import select, update, func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config import settings
from db.models import Base, Filter, Listing, NotificationLog, ScrapeRun

logger = logging.getLogger(__name__)

# ── ContextVar: current session bound to the running task ────
#
# Each asyncio Task gets its own slot in the ContextVar.
# Calling `get_session()` returns the session that was set
# by the innermost `session_context()` context manager in
# the current task — no passing session objects around manually.
_session_var: ContextVar[Optional[AsyncSession]] = ContextVar(
    "_session_var", default=None
)


def get_session() -> AsyncSession:
    """
    Return the AsyncSession for the current async context.
    Raises RuntimeError if called outside a `session_context()` block.
    """
    session = _session_var.get()
    if session is None:
        raise RuntimeError(
            "No database session in context. "
            "Wrap your code with `async with session_context():`"
        )
    return session


# ═══════════════════════════════════════════════════════════════
class DatabaseManager:
    """
    Owns the engine + session factory.
    Use the module-level `db` singleton — don't instantiate directly.
    """

    def __init__(self) -> None:
        self._engine:  Optional[AsyncEngine]           = None
        self._factory: Optional[async_sessionmaker]    = None

    # ── Lifecycle ─────────────────────────────────────────────

    async def init(self) -> None:
        """Create engine, session factory, and run DDL (create tables)."""
        self._engine = create_async_engine(
            settings.DATABASE_URL_asyncpg,
            **settings.engine_options,
        )
        self._factory = async_sessionmaker(
            bind        = self._engine,
            class_      = AsyncSession,
            expire_on_commit = False,   # keep attrs accessible after commit
            autoflush   = False,
        )
        # Create tables if they don't exist yet
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info(
            "Database ready: %s@%s:%s/%s",
            settings.DB_USER, settings.DB_HOST, settings.DB_PORT, settings.DB_NAME,
        )

    async def close(self) -> None:
        if self._engine:
            await self._engine.dispose()
            logger.info("Database engine disposed")

    # ── Context manager: bind session to ContextVar ───────────

    @asynccontextmanager
    async def session_context(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Opens a session, binds it to the ContextVar for this task,
        commits on clean exit, rolls back on exception.

        Usage:
            async with db.session_context():
                await listing_repo.upsert(apt)   # calls get_session() internally
        """
        if self._factory is None:
            raise RuntimeError("DatabaseManager not initialised — call await db.init() first")

        session: AsyncSession = self._factory()
        token = _session_var.set(session)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
            _session_var.reset(token)   # restore previous value (supports nesting)

    @asynccontextmanager
    async def nested_transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Savepoint-based nested transaction inside an existing session context.
        Useful for operations that must be atomic within a larger transaction.
        """
        session = get_session()
        async with session.begin_nested():
            yield session


# ── Module-level singleton ────────────────────────────────────
db = DatabaseManager()


# ═══════════════════════════════════════════════════════════════
# Repositories — thin wrappers that always call get_session()
# ═══════════════════════════════════════════════════════════════

class ListingRepository:
    """All DB operations related to the `listings` table."""

    async def upsert(self, apt) -> tuple[int, bool]:
        """
        INSERT … ON CONFLICT DO UPDATE.
        Returns (db_id, is_new).
        """
        session    = get_session()
        slug, ext  = apt.id.split(":", 1)

        stmt = (
            pg_insert(Listing)
            .values(
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
                first_seen_at = datetime.now(timezone.utc),
                last_seen_at  = datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                index_elements = ["source_slug", "external_id"],
                set_=dict(
                    last_seen_at = datetime.now(timezone.utc),
                    active       = True,
                    price        = apt.price,
                    title        = apt.title,
                ),
            )
            .returning(Listing.id, Listing.first_seen_at, Listing.last_seen_at)
        )
        row    = (await session.execute(stmt)).one()
        is_new = row.first_seen_at == row.last_seen_at   # same → just inserted
        return row.id, is_new

    async def mark_notified(
        self, listing_id: int, chat_id: str,
        success: bool = True, error_msg: str | None = None,
    ) -> None:
        session = get_session()
        await session.execute(
            update(Listing)
            .where(Listing.id == listing_id)
            .values(notified=True, notified_at=datetime.now(timezone.utc))
        )
        session.add(NotificationLog(
            listing_id = listing_id,
            chat_id    = chat_id,
            success    = success,
            error_msg  = error_msg,
        ))

    async def is_notified(self, uid: str) -> bool:
        session = get_session()
        row = (await session.execute(
            select(Listing.notified).where(Listing.uid == uid)
        )).scalar_one_or_none()
        return bool(row)

    async def total_count(self) -> int:
        session = get_session()
        return (await session.execute(select(func.count()).select_from(Listing))).scalar_one()

    async def count_today(self) -> int:
        session = get_session()
        return (await session.execute(
            select(func.count())
            .select_from(Listing)
            .where(func.date(Listing.first_seen_at) == func.current_date())
        )).scalar_one()

    async def price_stats(self) -> list[dict]:
        session = get_session()
        rows = (await session.execute(
            text("""
                SELECT source_slug, rooms,
                       COUNT(*)                     AS total,
                       ROUND(AVG(price)::numeric, 0)  AS avg_price,
                       MIN(price)                   AS min_price,
                       MAX(price)                   AS max_price
                FROM listings
                WHERE price IS NOT NULL AND active = TRUE
                GROUP BY source_slug, rooms
                ORDER BY source_slug, rooms
            """)
        )).mappings().all()
        return [dict(r) for r in rows]


class FilterRepository:
    """All DB operations related to the `filters` table."""

    async def save(self, chat_id: str, filt, paused: bool = False) -> None:
        session = get_session()
        stmt = (
            pg_insert(Filter)
            .values(
                chat_id          = chat_id,
                min_rooms        = filt.min_rooms,
                max_rooms        = filt.max_rooms,
                min_sqm          = filt.min_sqm,
                max_sqm          = filt.max_sqm,
                min_price        = filt.min_price,
                max_price        = filt.max_price,
                social_status    = filt.social_status,
                include_keywords = filt.include_keywords,
                exclude_keywords = filt.exclude_keywords,
                paused           = paused,
                updated_at       = datetime.now(timezone.utc),
            )
            .on_conflict_do_update(
                index_elements = ["chat_id"],
                set_=dict(
                    min_rooms        = filt.min_rooms,
                    max_rooms        = filt.max_rooms,
                    min_sqm          = filt.min_sqm,
                    max_sqm          = filt.max_sqm,
                    min_price        = filt.min_price,
                    max_price        = filt.max_price,
                    social_status    = filt.social_status,
                    include_keywords = filt.include_keywords,
                    exclude_keywords = filt.exclude_keywords,
                    paused           = paused,
                    updated_at       = datetime.now(timezone.utc),
                ),
            )
        )
        await session.execute(stmt)

    async def load(self, chat_id: str) -> Optional[tuple]:
        """Returns (ApartmentFilter, paused) or None."""
        from app_models import ApartmentFilter   # avoid circular at module level
        session = get_session()
        row = (await session.execute(
            select(Filter).where(Filter.chat_id == chat_id)
        )).scalar_one_or_none()
        if not row:
            return None
        filt = ApartmentFilter(
            min_rooms        = row.min_rooms,
            max_rooms        = row.max_rooms,
            min_sqm          = float(row.min_sqm)    if row.min_sqm    else None,
            max_sqm          = float(row.max_sqm)    if row.max_sqm    else None,
            min_price        = float(row.min_price)  if row.min_price  else None,
            max_price        = float(row.max_price)  if row.max_price  else None,
            social_status    = row.social_status,
            include_keywords = list(row.include_keywords or []),
            exclude_keywords = list(row.exclude_keywords or []),
        )
        return filt, row.paused


class ScrapeRunRepository:
    """Tracks per-scraper run health."""

    async def begin(self, source_slug: str) -> int:
        session = get_session()
        run = ScrapeRun(source_slug=source_slug)
        session.add(run)
        await session.flush()   # populate run.id without committing
        return run.id

    async def finish(
        self, run_id: int, found: int, new: int, error: str | None = None
    ) -> None:
        session = get_session()
        await session.execute(
            update(ScrapeRun)
            .where(ScrapeRun.id == run_id)
            .values(
                finished_at    = datetime.now(timezone.utc),
                listings_found = found,
                new_listings   = new,
                error_msg      = error,
                success        = (error is None),
            )
        )


# ── Convenience singletons ────────────────────────────────────
listing_repo  = ListingRepository()
filter_repo   = FilterRepository()
run_repo      = ScrapeRunRepository()