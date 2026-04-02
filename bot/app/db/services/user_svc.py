import datetime
import typing as t

from app.core.apartment import ApartmentFilter
from app.core.enums import SocialStatus
from app.db.models.models import Filter, User
from app.db.repositories.user_repo import UserRepository


class UserService:
    def __init__(self):
        self.repo = UserRepository()

    async def get_or_register_user(
        self,
        chat_id: str,
        username: t.Optional[str],
        full_name: t.Optional[str],
    ) -> User:
        user = await self.repo.get_user_with_filter(chat_id)
        if not user:
            user = await self.repo.create_user_with_filter(
                user_data={
                    "chat_id": chat_id,
                    "username": username,
                    "full_name": full_name,
                },
                filter_data={
                    "paused": False,
                    "min_price": None,
                    "max_price": None,
                    "social_status": SocialStatus.ANY.value,
                },
            )
        return user

    async def save_filter_state(
        self,
        chat_id: str,
        filt: ApartmentFilter,
        paused: bool,
    ) -> None:
        user = await self.repo.get_user_with_filter(chat_id)
        if user and user.filters:
            user.filters.paused = paused
            user.filters.min_price = filt.min_price
            user.filters.max_price = filt.max_price
            user.filters.min_rooms = filt.min_rooms
            user.filters.max_rooms = filt.max_rooms
            user.filters.min_sqm = filt.min_sqm
            user.filters.max_sqm = filt.max_sqm
            user.filters.social_status = filt.social_status.value

    async def update_language(self, chat_id: str, language: str) -> None:
        user = await self.repo.get_by_chat_id(chat_id)
        if user:
            user.language = language

    async def update_show_special_listings(self, chat_id: str, enabled: bool) -> None:
        user = await self.repo.get_by_chat_id(chat_id)
        if user:
            user.show_special_listings = enabled

    async def save_profile(
        self, chat_id: str, profile_data: dict[str, t.Any]
    ) -> User | None:
        user = await self.repo.get_by_chat_id(chat_id)
        if user is None:
            return None

        for field_name, value in profile_data.items():
            setattr(user, field_name, value)

        user.full_name = (
            " ".join(part for part in [user.first_name, user.last_name] if part).strip()
            or user.full_name
        )
        return user

    async def get_profile(self, chat_id: str) -> User | None:
        return await self.repo.get_by_chat_id(chat_id)

    @staticmethod
    def serialize_profile(user: User | None) -> dict[str, t.Any]:
        if user is None:
            return {
                "salutation": "",
                "first_name": "",
                "last_name": "",
                "email": "",
                "phone": "",
                "street": "",
                "house_number": "",
                "zip_code": "",
                "city": "",
                "persons_total": None,
                "wbs_available": False,
                "wbs_date": "",
                "wbs_rooms": None,
                "wbs_income": None,
            }

        return {
            "salutation": user.salutation or "",
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "email": user.email or "",
            "phone": user.phone or "",
            "street": user.street or "",
            "house_number": user.house_number or "",
            "zip_code": user.zip_code or "",
            "city": user.city or "",
            "persons_total": user.persons_total,
            "wbs_available": bool(user.wbs_available),
            "wbs_date": (
                user.wbs_date.isoformat()
                if isinstance(user.wbs_date, datetime.date)
                else ""
            ),
            "wbs_rooms": user.wbs_rooms,
            "wbs_income": user.wbs_income,
        }

    @staticmethod
    def is_profile_complete(data: dict[str, t.Any]) -> bool:
        if data.get("salutation") not in {"Herr", "Frau"}:
            return False
        for field_name in (
            "first_name",
            "last_name",
            "email",
            "phone",
            "street",
            "house_number",
            "zip_code",
            "city",
            "wbs_date",
        ):
            if not str(data.get(field_name, "")).strip():
                return False
        persons_total = data.get("persons_total")
        if not isinstance(persons_total, int) or persons_total < 1:
            return False
        wbs_rooms = data.get("wbs_rooms")
        if not isinstance(wbs_rooms, int) or wbs_rooms < 1 or wbs_rooms > 7:
            return False
        if data.get("wbs_income") not in {100, 140, 160, 180, 220}:
            return False
        return isinstance(data.get("wbs_available"), bool)

    @staticmethod
    def convert_to_domain(db_filter: Filter) -> ApartmentFilter:
        return ApartmentFilter(
            min_price=(
                float(db_filter.min_price) if db_filter.min_price is not None else None
            ),
            max_price=(
                float(db_filter.max_price) if db_filter.max_price is not None else None
            ),
            min_rooms=db_filter.min_rooms,
            max_rooms=db_filter.max_rooms,
            min_sqm=float(db_filter.min_sqm) if db_filter.min_sqm is not None else None,
            max_sqm=float(db_filter.max_sqm) if db_filter.max_sqm is not None else None,
            social_status=SocialStatus(db_filter.social_status),
        )
