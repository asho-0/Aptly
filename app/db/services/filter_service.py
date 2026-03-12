# ============================================================
# services/filter_service.py — Filter business logic
#
# Translates between:
#   • ApartmentFilter (in-memory domain model used by scrapers)
#   • FilterResponse  (DB-loaded schema)
#   • SaveFilterRequest (DB-write schema)
# Also owns validation rules that go beyond Pydantic field-level checks.
# ============================================================

import logging
from typing import Optional

from app_models import ApartmentFilter
from config import settings
from database import db
from repositories.filter import FilterRepository
from schemas.filter import (
    FilterResponse,
    LoadFilterRequest,
    SaveFilterRequest,
    SetPausedRequest,
    UpdateFilterFieldRequest,
    UpdateKeywordsRequest,
)

logger = logging.getLogger(__name__)


class FilterService:
    """
    All filter read/write operations go through here.
    Called by bot_commands.FilterStore and main.py startup.
    """

    def __init__(self) -> None:
        self._repo = FilterRepository()

    async def load(self, chat_id: str) -> Optional[tuple[ApartmentFilter, bool]]:
        """
        Load filter from DB and convert to in-memory ApartmentFilter.
        Returns (filter, paused) or None if no saved filter exists.
        """
        req = LoadFilterRequest(chat_id=chat_id)
        async with db.session_context():
            response: Optional[FilterResponse] = await self._repo.load(req)

        if response is None:
            logger.info("No saved filter found for chat_id=%s — using defaults", chat_id)
            return None

        filt = ApartmentFilter(
            min_rooms        = response.min_rooms,
            max_rooms        = response.max_rooms,
            min_sqm          = response.min_sqm,
            max_sqm          = response.max_sqm,
            min_price        = response.min_price,
            max_price        = response.max_price,
            social_status    = response.social_status,
            include_keywords = response.include_keywords,
            exclude_keywords = response.exclude_keywords,
        )
        logger.info("Filter loaded from database for chat_id=%s", chat_id)
        return filt, response.paused

    async def save(self, chat_id: str, filt: ApartmentFilter, paused: bool) -> None:
        """Persist in-memory filter to DB."""
        req = SaveFilterRequest(
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
        )
        async with db.session_context():
            await self._repo.save(req)
        logger.debug("Filter persisted for chat_id=%s paused=%s", chat_id, paused)

    async def apply_range_update(
        self,
        filt:      ApartmentFilter,
        chat_id:   str,
        field:     str,
        args:      list[str],
        cast:      type,
    ) -> bool:
        """
        Parse 1 or 2 args into a min/max range, apply to filt in-place,
        validate, and persist. Returns False if args are invalid.
        """
        field_map = {
            "rooms": ("min_rooms", "max_rooms"),
            "price": ("min_price", "max_price"),
            "area":  ("min_sqm",   "max_sqm"),
        }
        if field not in field_map:
            return False

        min_attr, max_attr = field_map[field]
        try:
            if len(args) >= 2:
                setattr(filt, min_attr, cast(args[0]))
                setattr(filt, max_attr, cast(args[1]))
            elif len(args) == 1:
                setattr(filt, min_attr, cast(args[0]))
                setattr(filt, max_attr, None)
            else:
                return False
        except (ValueError, IndexError):
            return False

        # Validate the resulting range via SaveFilterRequest
        try:
            SaveFilterRequest(
                chat_id       = chat_id,
                min_rooms     = filt.min_rooms,   max_rooms = filt.max_rooms,
                min_sqm       = filt.min_sqm,     max_sqm   = filt.max_sqm,
                min_price     = filt.min_price,   max_price = filt.max_price,
                social_status = filt.social_status,
            )
        except Exception as exc:
            logger.warning("Range validation failed for field=%s: %s", field, exc)
            return False

        await self.save(chat_id, filt, paused=False)
        return True

    async def apply_status_update(
        self, filt: ApartmentFilter, chat_id: str, value: str
    ) -> bool:
        """Set social_status, validate, and persist."""
        try:
            SaveFilterRequest(chat_id=chat_id, social_status=value)
        except Exception:
            return False
        filt.social_status = value
        await self.save(chat_id, filt, paused=False)
        return True

    async def apply_keyword_update(
        self,
        filt:    ApartmentFilter,
        chat_id: str,
        req:     UpdateKeywordsRequest,
    ) -> None:
        """Add/remove keywords and persist."""
        for word in req.add:
            w = word.lower()
            if w and w not in filt.include_keywords:
                filt.include_keywords.append(w)
        for word in req.remove:
            w = word.lower()
            filt.include_keywords = [k for k in filt.include_keywords if k != w]
            if w not in filt.exclude_keywords:
                filt.exclude_keywords.append(w)
        await self.save(chat_id, filt, paused=False)

    async def set_paused(
        self, filt: ApartmentFilter, chat_id: str, paused: bool
    ) -> None:
        await self.save(chat_id, filt, paused=paused)
        logger.info("Notifications %s for chat_id=%s", "paused" if paused else "resumed", chat_id)

    def build_default(self) -> ApartmentFilter:
        """Construct the default filter from .env settings."""
        return ApartmentFilter(
            min_rooms        = settings.FILTER_MIN_ROOMS,
            max_rooms        = settings.FILTER_MAX_ROOMS,
            min_sqm          = settings.FILTER_MIN_SQM,
            max_sqm          = settings.FILTER_MAX_SQM,
            min_price        = settings.FILTER_MIN_PRICE,
            max_price        = settings.FILTER_MAX_PRICE,
            social_status    = settings.FILTER_SOCIAL_STATUS,
            include_keywords = settings.include_keywords_list,
            exclude_keywords = settings.exclude_keywords_list,
        )