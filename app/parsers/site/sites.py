import asyncio
import logging
from typing import cast
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from app.core.apartment import Apartment
from app.config import settings
from app.parsers.base.base import BaseScraper
from app.parsers.utils.de_parsing import (
    detect_social_housing_status,
    parse_german_price,
    parse_german_room_count,
    parse_german_sqm,
)
from app.parsers.urls import (
    DEGEWO_LISTINGS_URL,
    GEWOBAG_LISTINGS_URL,
    WBM_LISTINGS_URL,
)

logger = logging.getLogger(__name__)


class DegewoScraper(BaseScraper):
    slug, name, base_url = "degewo", "Degewo", DEGEWO_LISTINGS_URL

    async def fetch_all(self) -> list[Apartment]:
        html = await self._fetch(self.base_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        results: list[Apartment] = self.parse_listings(soup, self.base_url)

        form = soup.select_one("form.openimmo-search-form")
        if not form:
            return results

        tokens: dict[str, str] = {}
        for inp in form.select("input[type=hidden]"):
            name_attr = inp.get("name")
            val_attr = inp.get("value")
            if isinstance(name_attr, str) and isinstance(val_attr, str):
                tokens[name_attr] = val_attr

        action_attr = form.get("action", "/immosuche")
        action = urljoin(self.domain, cast(str, action_attr))

        for page in range(2, self.MAX_PAGES + 1):
            await asyncio.sleep(settings.REQUEST_DELAY)
            data = {
                **tokens,
                "tx_openimmo_immobilie[page]": str(page),
                "tx_openimmo_immobilie[search]": "search",
            }
            page_html = await self._post(action, data=data)
            if not page_html:
                break

            p_soup = BeautifulSoup(page_html, "lxml")
            listings = self.parse_listings(p_soup, action)
            if not listings:
                break
            results.extend(listings)
        return results

    def parse_listings(self, soup: BeautifulSoup, page_url: str) -> list[Apartment]:
        apartments: list[Apartment] = []
        for card in soup.select("article.article-list__item--immosearch"):
            try:
                id_attr = card.get("id", "")
                uid: str = str(id_attr).split("-")[-1] if id_attr else "unknown"

                link = card.select_one("a[href]")
                href = link.get("href") if link else None
                full_url = (
                    urljoin(self.domain, href) if isinstance(href, str) else page_url
                )

                meta = self.extract_text(card, ".article__meta")
                address, _, district = meta.partition(" | ")
                props_text = self.extract_text(card, ".article__properties")

                apartments.append(
                    Apartment(
                        id=self.make_id(uid),
                        source=self.name,
                        url=full_url,
                        title=self.extract_text(card, ".article__title"),
                        price=parse_german_price(self.extract_text(card, ".price")),
                        rooms=parse_german_room_count(props_text),
                        sqm=parse_german_sqm(props_text),
                        address=address.strip(),
                        district=district.strip(),
                        social_status=detect_social_housing_status(
                            props_text + self.extract_text(card, ".article__tags")
                        ),
                    )
                )
            except Exception as e:
                logger.warning("[%s] Skip card: %s", self.slug, e)
        return apartments


class GewobagScraper(BaseScraper):
    slug, name, base_url = "gewobag", "Gewobag", GEWOBAG_LISTINGS_URL

    async def fetch_all(self) -> list[Apartment]:
        return await self.paginate_simple(
            "a:-soup-contains('Weiter'), a:-soup-contains('»')"
        )

    def parse_listings(self, soup: BeautifulSoup, page_url: str) -> list[Apartment]:
        apartments: list[Apartment] = []
        for card in soup.select("article.gw-offer"):
            try:
                link = card.select_one("a[href]")
                href = link.get("href") if link else None
                if not isinstance(href, str):
                    continue

                full_url = urljoin(self.domain, href)
                uid: str = full_url.strip("/").split("/")[-1]

                content = card.select_one(".gw-offer__content")
                area_text = self.extract_text(content, ".angebot-area td")

                apartments.append(
                    Apartment(
                        id=self.make_id(uid),
                        source=self.name,
                        url=full_url,
                        title=self.extract_text(content, ".angebot-title"),
                        price=parse_german_price(
                            self.extract_text(content, ".angebot-kosten td")
                        ),
                        rooms=parse_german_room_count(area_text),
                        sqm=parse_german_sqm(area_text),
                        address=self.extract_text(content, "address"),
                        district=self.extract_text(content, ".angebot-region")
                        .replace("Bezirk", "")
                        .strip(),
                        social_status=detect_social_housing_status(full_url),
                    )
                )
            except Exception as e:
                logger.warning("[%s] Skip: %s", self.slug, e)
        return apartments


class WBMScraper(BaseScraper):
    slug, name, base_url = "wbm", "WBM", WBM_LISTINGS_URL

    async def fetch_all(self) -> list[Apartment]:
        return await self.paginate_simple(
            "a:-soup-contains('Weiter'), a:-soup-contains('next')"
        )

    def parse_listings(self, soup: BeautifulSoup, page_url: str) -> list[Apartment]:
        apartments: list[Apartment] = []
        cards = soup.select(".immo-teaser, .objekt-teaser, .textWrap")
        for card in cards:
            try:
                link = card.select_one("a[href]")
                href = link.get("href") if link else None
                if not isinstance(href, str):
                    continue

                full_url = urljoin(self.domain, href)
                uid: str = full_url.strip("/").split("/")[-1]
                full_text = card.get_text(" ", strip=True)

                apartments.append(
                    Apartment(
                        id=self.make_id(uid),
                        source=self.name,
                        url=full_url,
                        title=self.extract_text(card, "h1, h2, h3, h4"),
                        price=parse_german_price(
                            self.extract_text(card, ".main-property-rent") or full_text
                        ),
                        rooms=parse_german_room_count(
                            self.extract_text(card, ".main-property-rooms") or full_text
                        ),
                        sqm=parse_german_sqm(
                            self.extract_text(card, ".main-property-size") or full_text
                        ),
                        address=self.extract_text(card, ".address"),
                        district="",
                        social_status=detect_social_housing_status(full_text),
                    )
                )
            except Exception as e:
                logger.warning("[%s] Skip: %s", self.slug, e)
        return apartments
