# ============================================================
# repositories/base.py — Base repository providing session access
# ============================================================

from sqlalchemy.ext.asyncio import AsyncSession
from database import get_session

class BaseRepository:
    """Provides dynamic session resolution via ContextVar."""
    
    @property
    def session(self) -> AsyncSession:
        return get_session()