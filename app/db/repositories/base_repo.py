from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session


class BaseRepository:
    @property
    def session(self) -> AsyncSession:
        return get_session()
