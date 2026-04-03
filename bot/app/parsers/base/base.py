import logging
import typing as t
from abc import ABC, abstractmethod
from types import TracebackType
from urllib.parse import urlparse

from app.core.apartment import Apartment

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    slug: str = ""
    name: str = ""
    base_url: str = ""
    MAX_PAGES = 50

    def __init__(self) -> None:
        self._domain: str | None = None

    @property
    def domain(self) -> str:
        if self._domain is None:
            parsed = urlparse(self.base_url)
            self._domain = f"{parsed.scheme}://{parsed.netloc}"
        return self._domain

    async def close_session(self) -> None:
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type: t.Optional[t.Type[BaseException]],
        exc_val: t.Optional[BaseException],
        exc_tb: t.Optional[TracebackType],
    ) -> None:
        await self.close_session()

    def make_id(self, uid: str) -> str:
        return f"{self.slug}:{uid}"

    @abstractmethod
    async def fetch_all(self) -> list[Apartment]:
        pass
