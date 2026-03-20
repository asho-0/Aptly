import json
import logging
import typing as t

import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from app.core.config import settings
from app.core.apartment import Apartment
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
    HOWOGE_BASE_URL,
    HOWOGE_LIST_URL,
)

logger = logging.getLogger(__name__)


class DegewoScraper(BaseScraper):
    slug, name, base_url = "degewo", "Degewo", DEGEWO_LISTINGS_URL

    async def fetch_all(self) -> list[Apartment]:
        html = await self._fetch(self.base_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "lxml")
        results = self.parse_listings(soup, self.base_url)

        form = soup.select_one("form.openimmo-search-form")
        if not form:
            return results

        tokens: dict[str, str] = {
            str(inp["name"]): str(inp["value"])
            for inp in form.select("input[type=hidden]")
            if inp.has_attr("name") and inp.has_attr("value")
        }
        action = urljoin(self.domain, t.cast(str, form.get("action", "/immosuche")))

        for page in range(2, self.MAX_PAGES + 1):
            await asyncio.sleep(settings.REQUEST_DELAY)
            page_html = await self._post(action, data={
                **tokens,
                "tx_openimmo_immobilie[page]": str(page),
                "tx_openimmo_immobilie[search]": "search",
            })
            if not page_html:
                break
            listings = self.parse_listings(BeautifulSoup(page_html, "lxml"), action)
            if not listings:
                break
            results.extend(listings)

        return results

    def parse_listings(self, soup: BeautifulSoup, page_url: str) -> list[Apartment]:
        apartments: list[Apartment] = []
        for card in soup.select("article.article-list__item--immosearch"):
            try:
                uid = str(card.get("id", "unknown")).split("-")[-1]
                link = card.select_one("a[href]")
                href = link.get("href") if link else None
                full_url = urljoin(self.domain, href) if isinstance(href, str) else page_url
                address, _, district = self.extract_text(card, ".article__meta").partition(" | ")
                props_text = self.extract_text(card, ".article__properties")

                apartments.append(Apartment(
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
                ))
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
                content = card.select_one(".gw-offer__content")
                area_text = self.extract_text(content, ".angebot-area td")

                apartments.append(Apartment(
                    id=self.make_id(full_url.strip("/").split("/")[-1]),
                    source=self.name,
                    url=full_url,
                    title=self.extract_text(content, ".angebot-title"),
                    price=parse_german_price(self.extract_text(content, ".angebot-kosten td")),
                    rooms=parse_german_room_count(area_text),
                    sqm=parse_german_sqm(area_text),
                    address=self.extract_text(content, "address"),
                    district=self.extract_text(content, ".angebot-region").replace("Bezirk", "").strip(),
                    social_status=detect_social_housing_status(full_url),
                ))
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
        for card in soup.select(".immo-teaser, .objekt-teaser, .textWrap"):
            try:
                link = card.select_one("a[href]")
                href = link.get("href") if link else None
                if not isinstance(href, str):
                    continue

                full_url = urljoin(self.domain, href)
                full_text = card.get_text(" ", strip=True)

                apartments.append(Apartment(
                    id=self.make_id(full_url.strip("/").split("/")[-1]),
                    source=self.name,
                    url=full_url,
                    title=self.extract_text(card, "h1, h2, h3, h4"),
                    price=parse_german_price(self.extract_text(card, ".main-property-rent") or full_text),
                    rooms=parse_german_room_count(self.extract_text(card, ".main-property-rooms") or full_text),
                    sqm=parse_german_sqm(self.extract_text(card, ".main-property-size") or full_text),
                    address=self.extract_text(card, ".address"),
                    district="",
                    social_status=detect_social_housing_status(full_text),
                ))
            except Exception as e:
                logger.warning("[%s] Skip: %s", self.slug, e)
        return apartments



class HowogeScraper(BaseScraper):
    slug, name, base_url = "howoge", "Howoge", HOWOGE_LIST_URL

    async def fetch_all(self) -> list[Apartment]:
        raw = await self._post(HOWOGE_LIST_URL, data={})
        if not raw:
            return []

        try:
            data: dict[str, t.Any] = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("[%s] JSON parse error: %s", self.slug, exc)
            return []

        apartments = [
            apt
            for obj in data.get("immoobjects", [])
            if (apt := self._parse_obj(obj)) is not None
        ]
        logger.info("[%s] Parsed %d listings", self.slug, len(apartments))
        return apartments

    def parse_listings(self, soup: BeautifulSoup, page_url: str) -> list[Apartment]:
        return []

    def _parse_obj(self, obj: dict[str, t.Any]) -> Apartment | None:
        try:
            uid: str = str(obj["uid"])

            link: str = obj.get("link", "")
            url: str = HOWOGE_BASE_URL + link if link.startswith("/") else link

            image_path: str = obj.get("image", "")
            image_url: str | None = (
                HOWOGE_BASE_URL + image_path if image_path.startswith("/")
                else image_path or None
            )

            address: str = obj.get("title", "")
            district: str = obj.get("district", "")

            price: float | None = float(obj.get("rent") or 0) or None
            sqm: float | None = float(obj.get("area") or 0) or None
            rooms: int | None = int(obj.get("rooms") or 0) or None

            social_probe: str = " ".join([
                obj.get("wbs", "nein"),
                obj.get("notice", ""),
                " ".join(obj.get("features", [])),
            ])

            return Apartment(
                id=self.make_id(uid),
                source=self.name,
                url=url,
                title=address,
                price=price,
                rooms=rooms,
                sqm=sqm,
                address=address,
                district=district,
                image_url=image_url,
                social_status=detect_social_housing_status(social_probe),
            )
        except Exception as exc:
            logger.warning("[%s] Skip obj: %s", self.slug, exc)
            return None