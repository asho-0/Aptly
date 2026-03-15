import typing as t
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models.models import User, Filter
from app.db.repositories.base_repo import BaseRepository

class UserRepository(BaseRepository):
    async def get_user_with_filter(self, chat_id: str) -> User | None:
        query = (
            select(User)
            .options(selectinload(User.filter))
            .where(User.chat_id == chat_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_user_with_filter(
        self, 
        user_data: dict[str, t.Any], 
        filter_data: dict[str, t.Any]
    ) -> User:
        user = User(**user_data)
        self.session.add(user)
        await self.session.flush()
        
        user_filter = Filter(chat_id=user.chat_id, **filter_data)
        self.session.add(user_filter)
        user.filter = user_filter
        return user

    async def get_all_active_users(self) -> t.Sequence[User]:
        query = select(User).options(selectinload(User.filter)).where(User.is_active == True)
        return (await self.session.execute(query)).scalars().all()