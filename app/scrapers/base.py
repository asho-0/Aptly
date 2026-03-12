# ============================================================
# scrapers/base.py — Abstract base scraper
# ============================================================

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import AsyncIterator

import aiohttp
from bs4 import BeautifulSoup

from config import settings
from app_models import Apartment

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Every concrete scraper must:
      • set  `slug`  (unique short name, e.g. "zillow")
      • set  `name`  (human-readable, e.g. "Zillow")
      • set  `base_url`
      • implement  `parse_listings(soup, page_url) -> list[Apartment]`
      • optionally override `listing_urls()` to yield paginated URLs
    """

    slug:     str = ""
    name:     str = ""
    base_url: str = ""

    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    # ── Override to provide one or more URLs to scrape ──────
    async def listing_urls(self) -> AsyncIterator[str]:
        yield self.base_url

    # ── Implement the HTML → Apartment list parsing ─────────
    @abstractmethod
    def parse_listings(self, soup: BeautifulSoup, page_url: str) -> list[Apartment]:
        ...

    # ── Public API used by the scheduler ────────────────────
    async def fetch_all(self) -> list[Apartment]:
        results: list[Apartment] = []
        async for url in self.listing_urls():
            html = await self._fetch(url)
            if html is None:
                continue
            soup = BeautifulSoup(html, "lxml")
            try:
                listings = self.parse_listings(soup, url)
                results.extend(listings)
                logger.info("[%s] scraped %d listings from %s", self.slug, len(listings), url)
            except Exception as exc:
                logger.exception("[%s] parse error on %s: %s", self.slug, url, exc)
            await asyncio.sleep(settings.REQUEST_DELAY)
        return results

    # ── Internal HTTP helper ─────────────────────────────────
    async def _fetch(self, url: str, attempt: int = 1) -> str | None:
        try:
            async with self.session.get(
                url,
                headers=settings.HEADERS,
                timeout=aiohttp.ClientTimeout(total=settings.REQUEST_TIMEOUT),
            ) as resp:
                if resp.status == 200:
                    return await resp.text()
                logger.warning("[%s] HTTP %d for %s", self.slug, resp.status, url)
        except asyncio.TimeoutError:
            logger.warning("[%s] timeout on %s (attempt %d)", self.slug, url, attempt)
        except aiohttp.ClientError as exc:
            logger.warning("[%s] client error on %s: %s", self.slug, url, exc)

        if attempt < settings.MAX_RETRIES:
            await asyncio.sleep(2 ** attempt)
            return await self._fetch(url, attempt + 1)
        return None

    # ── Convenience helpers ──────────────────────────────────
    @staticmethod
    def safe_text(tag) -> str:
        return tag.get_text(strip=True) if tag else ""

    @staticmethod
    def safe_float(text: str) -> float | None:
        import re
        m = re.search(r"[\d,]+\.?\d*", text.replace(" ", "").replace("\xa0", ""))
        if m:
            try:
                return float(m.group().replace(",", ""))
            except ValueError:
                pass
        return None

    @staticmethod
    def safe_int(text: str) -> int | None:
        import re
        m = re.search(r"\d+", text)
        return int(m.group()) if m else None

    def make_id(self, listing_id: str) -> str:
        return f"{self.slug}:{listing_id}"