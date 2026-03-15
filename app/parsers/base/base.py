import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import urlparse, urljoin

import aiohttp
from bs4 import BeautifulSoup, Tag

import app.seen as seen
from app.config import settings
from app.core.apartment import Apartment

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    slug: str = ""
    name: str = ""
    base_url: str = ""
    MAX_PAGES = 5

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None
        self._domain: str | None = None

    @property
    def domain(self) -> str:
        if self._domain is None:
            parsed = urlparse(self.base_url)
            self._domain = f"{parsed.scheme}://{parsed.netloc}"
        return self._domain

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(
                connector=connector, headers=settings.HEADERS
            )
        return self._session

    async def close_session(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def make_id(self, uid: str) -> str:
        return f"{self.slug}:{uid}"

    def extract_text(self, element: Tag | None, selector: str | None = None) -> str:
        if not element:
            return ""
        target = element.select_one(selector) if selector else element
        return target.get_text(separator=" ", strip=True) if target else ""

    async def _request(
        self, method: str, url: str, attempt: int = 1, **kwargs: Any
    ) -> str | None:
        try:
            timeout = aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT)
            async with self.session.request(
                method, url, timeout=timeout, **kwargs
            ) as resp:
                if resp.status == 200:
                    return await resp.text()
                logger.warning(
                    "[%s] %s HTTP %d for %s", self.slug, method, resp.status, url
                )
        except Exception as exc:
            logger.warning(
                "[%s] %s error %s: %s (att %d)", self.slug, method, url, exc, attempt
            )

        if attempt < settings.MAX_RETRIES:
            await asyncio.sleep(2**attempt)
            return await self._request(method, url, attempt + 1, **kwargs)
        return None

    async def _fetch(self, url: str) -> str | None:
        return await self._request("GET", url)

    async def _post(self, url: str, data: dict[str, str]) -> str | None:
        return await self._request("POST", url, data=data)

    async def paginate_simple(self, next_selector: str) -> list[Apartment]:
        results: list[Apartment] = []
        current_url: str = self.base_url

        for _ in range(self.MAX_PAGES):
            html = await self._fetch(current_url)
            if not html:
                break

            soup = BeautifulSoup(html, "lxml")
            results.extend(self.parse_listings(soup, current_url))

            next_link = soup.select_one(next_selector)
            if not next_link:
                break

            href = next_link.get("href")
            if not isinstance(href, str):
                break

            current_url = urljoin(self.domain, href).split("#")[0]
            await asyncio.sleep(settings.REQUEST_DELAY)
        return results

    @abstractmethod
    def parse_listings(self, soup: BeautifulSoup, page_url: str) -> list[Apartment]:
        pass

    @abstractmethod
    async def fetch_all(self) -> list[Apartment]:
        pass

    async def fetch_incremental(self) -> list[Apartment]:
        try:
            all_apartments = await self.fetch_all()
            unique_map = {apt.id: apt for apt in all_apartments}
            new_apartments = [
                apt for aid, apt in unique_map.items() if seen.is_new(aid)
            ]
            logger.info(
                "[%s] Found %d total. New: %d",
                self.slug,
                len(all_apartments),
                len(new_apartments),
            )
            return new_apartments
        finally:
            await self.close_session()
