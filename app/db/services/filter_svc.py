import logging
from typing import Optional

from app.db.session import db
from app.config import settings
from app.core.apartment import ApartmentFilter
from app.core.enums import SocialStatus
from app.db.repositories.filter_repo import FilterRepository
from app.db.schemas.filter_scm import (
    FilterResponse,
    LoadFilterRequest,
    SaveFilterRequest,
)

logger = logging.getLogger(__name__)


async def load_filter(chat_id: str) -> Optional[tuple[ApartmentFilter, bool]]:
    req = LoadFilterRequest(chat_id=chat_id)
    async with db.session_context():
        repo = FilterRepository()
        response: Optional[FilterResponse] = await repo.load(req)

    if response is None:
        logger.info("No saved filter for chat_id=%s — using defaults", chat_id)
        return None

    filt = ApartmentFilter(
        min_rooms=response.min_rooms,
        max_rooms=response.max_rooms,
        min_sqm=response.min_sqm,
        max_sqm=response.max_sqm,
        min_price=response.min_price,
        max_price=response.max_price,
        social_status=SocialStatus(response.social_status),
    )
    logger.info("Filter loaded from DB for chat_id=%s", chat_id)
    return filt, response.paused


async def save_filter(chat_id: str, filt: ApartmentFilter, paused: bool) -> None:
    req = SaveFilterRequest(
        chat_id=chat_id,
        min_rooms=filt.min_rooms,
        max_rooms=filt.max_rooms,
        min_sqm=filt.min_sqm,
        max_sqm=filt.max_sqm,
        min_price=filt.min_price,
        max_price=filt.max_price,
        social_status=filt.social_status,
        paused=paused,
    )
    async with db.session_context():
        repo = FilterRepository()
        await repo.save(req)
    logger.debug("Filter persisted for chat_id=%s paused=%s", chat_id, paused)


def build_default_filter() -> ApartmentFilter:
    return ApartmentFilter(
        min_rooms=settings.FILTER_MIN_ROOMS,
        max_rooms=settings.FILTER_MAX_ROOMS,
        min_sqm=settings.FILTER_MIN_SQM,
        max_sqm=settings.FILTER_MAX_SQM,
        min_price=settings.FILTER_MIN_PRICE,
        max_price=settings.FILTER_MAX_PRICE,
        social_status=SocialStatus(settings.FILTER_SOCIAL_STATUS),
    )


async def apply_range_update(
    filt: ApartmentFilter,
    chat_id: str,
    field: str,
    args: list[str],
    cast_type: type,
) -> bool:
    field_map = {
        "rooms": ("min_rooms", "max_rooms"),
        "price": ("min_price", "max_price"),
        "area": ("min_sqm", "max_sqm"),
    }
    if field not in field_map:
        return False

    min_attr, max_attr = field_map[field]
    try:
        if len(args) >= 2:
            setattr(filt, min_attr, cast_type(args[0]))
            setattr(filt, max_attr, cast_type(args[1]))
        elif len(args) == 1:
            setattr(filt, min_attr, cast_type(args[0]))
            setattr(filt, max_attr, None)
        else:
            return False
    except (ValueError, IndexError):
        return False

    try:
        SaveFilterRequest(
            chat_id=chat_id,
            min_rooms=filt.min_rooms,
            max_rooms=filt.max_rooms,
            min_sqm=filt.min_sqm,
            max_sqm=filt.max_sqm,
            min_price=filt.min_price,
            max_price=filt.max_price,
            social_status=filt.social_status,
        )
    except Exception as exc:
        logger.warning("Range validation failed for field=%s: %s", field, exc)
        return False
    await save_filter(chat_id, filt, paused=False)
    return True


async def apply_status_update(
    filt: ApartmentFilter,
    chat_id: str,
    value: SocialStatus,
) -> bool:
    try:
        SaveFilterRequest(chat_id=chat_id, social_status=value)
    except Exception:
        return False
    filt.social_status = value
    await save_filter(chat_id, filt, paused=False)
    return True
