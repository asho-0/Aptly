import logging
from typing import Optional, Tuple

from app.core.apartment import ApartmentFilter
from app.core.enums import SocialStatus
from app.db.repositories.filter_repo import FilterRepository
from app.db.schemas.filter_scm import (
    FilterResponse,
    LoadFilterRequest,
    SaveFilterRequest,
)

logger = logging.getLogger(__name__)


class FilterService:
    def __init__(self):
        self.repo = FilterRepository()

    def build_default_filter(self) -> ApartmentFilter:
        return ApartmentFilter(
            min_rooms=None,
            max_rooms=None,
            min_sqm=None,
            max_sqm=None,
            min_price=None,
            max_price=None,
            social_status=SocialStatus.ANY,
        )

    async def load_filter(
        self, chat_id: str
    ) -> Optional[Tuple[ApartmentFilter, bool, str]]:
        response: Optional[FilterResponse] = await self.repo.load(
            LoadFilterRequest(chat_id=chat_id)
        )

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
        lang = getattr(response, "lang", None) or "en"
        return filt, response.paused, lang

    async def save_filter(
        self,
        chat_id: str,
        filt: ApartmentFilter,
        paused: bool,
        lang: str = "en",
    ) -> None:
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
            lang=lang,
        )
        await self.repo.save(req)
        logger.debug(
            "Filter persisted for chat_id=%s paused=%s lang=%s", chat_id, paused, lang
        )

    async def apply_range_update(
        self,
        filt: ApartmentFilter,
        chat_id: str,
        field: str,
        args: list[str],
        cast_type: type,
        lang: str = "en",
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

        await self.save_filter(chat_id, filt, paused=False, lang=lang)
        return True

    async def apply_status_update(
        self,
        filt: ApartmentFilter,
        chat_id: str,
        value: SocialStatus,
        lang: str = "en",
    ) -> bool:
        filt.social_status = value
        await self.save_filter(chat_id, filt, paused=False, lang=lang)
        return True
