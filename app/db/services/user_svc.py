from typing import Optional
from app.core.apartment import ApartmentFilter
from app.core.enums import SocialStatus
from app.db.models.models import User, Filter
from app.db.repositories.user_repo import UserRepository


class UserService:
    def __init__(self):
        self.repo = UserRepository()

    async def get_or_register_user(
        self, chat_id: str, username: Optional[str], full_name: Optional[str]
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
        self, chat_id: str, filt: ApartmentFilter, paused: bool
    ) -> None:
        user = await self.repo.get_user_with_filter(chat_id)
        if user and user.filter:
            f = user.filter
            f.paused = paused
            f.min_price = filt.min_price
            f.max_price = filt.max_price
            f.min_rooms = filt.min_rooms
            f.max_rooms = filt.max_rooms
            f.min_sqm = filt.min_sqm
            f.max_sqm = filt.max_sqm
            f.social_status = filt.social_status.value

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
