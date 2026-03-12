# ============================================================
# scrapers/german_sites.py — 5 German real-estate scrapers
#
# Targets: ImmobilienScout24, Immowelt, WG-Gesucht, eBay Kleinanzeigen,
#          Sozialwohnungen.de (social housing portal)
#
# NOTE: CSS selectors are illustrative. Adjust to real HTML as needed.
# German text patterns and AMI/WBS terminology are correctly handled.
# ============================================================

import re
from urllib.parse import urljoin
from typing import AsyncIterator

from bs4 import BeautifulSoup

from telegram.models import Apartment
from scrapers.base import BaseScraper


# ── German text helpers ──────────────────────────────────────

def de_price(text: str) -> float | None:
    """Parse German price format: '1.250,00 €' → 1250.0"""
    text = text.replace(".", "").replace(",", ".").replace("€", "").replace("EUR", "").strip()
    import re
    m = re.search(r"[\d]+\.?\d*", text)
    try:
        return float(m.group()) if m else None
    except ValueError:
        return None


def de_sqm(text: str) -> float | None:
    """Parse German area: '78,5 m²' or '78.5 m²' → 78.5"""
    text = text.replace(",", ".").replace("m²", "").replace("qm", "").strip()
    m = re.search(r"[\d]+\.?\d*", text)
    try:
        return float(m.group()) if m else None
    except ValueError:
        return None


def de_rooms(text: str) -> int | None:
    """Parse '3 Zimmer', '3-Zimmer', '3 Zi.' etc → 3"""
    m = re.search(r"(\d+)[,.]?5?\s*[Zz]i", text)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*[Zz]immer", text)
    if m:
        return int(m.group(1))
    m = re.search(r"^(\d+)\s*$", text.strip())
    if m:
        return int(m.group(1))
    return None


def detect_social_status(text: str) -> str:
    """Detect German social housing keywords."""
    t = text.lower()
    if "wbs" in t or "wohnberechtigungsschein" in t:
        return "wbs"
    if "sozialwohnung" in t or "sozialer wohnungsbau" in t:
        return "sozialwohnung"
    if "staffelmiete" in t:
        return "staffelmiete"
    if "geförder" in t or "öffentlich gefördert" in t:
        return "sozialwohnung"
    return "market"


# ─────────────────────────────────────────────────────────────
# 1. ImmobilienScout24
# ─────────────────────────────────────────────────────────────
class ImmobilienScout24Scraper(BaseScraper):
    """
    https://www.immobilienscout24.de/Suche/de/wohnung-mieten
    Card structure:
      <article data-id="12345678" class="result-list__listing">
        <a href="/expose/12345678">
        <dl class="result-list-entry__primary-criterion">
          <dd class="result-list-entry__primary-criterion"> 1.250 € </dd>  ← Kaltmiete
          <dd class="result-list-entry__primary-criterion"> 78,50 m² </dd> ← Fläche
          <dd class="result-list-entry__primary-criterion"> 3 Zimmer </dd> ← Zimmer
        </dl>
        <div class="result-list-entry__address"> Musterstr. 5, 10115 Berlin </div>
        <p class="result-list-entry__brand-title"> Schöne 3-Zimmer-Wohnung </p>
      </article>
    """

    slug     = "is24"
    name     = "ImmobilienScout24"
    base_url = "https://www.immobilienscout24.de/Suche/de/wohnung-mieten"

    async def listing_urls(self) -> AsyncIterator[str]:
        for pg in range(1, 4):
            yield f"{self.base_url}?pagenumber={pg}"

    def parse_listings(self, soup: BeautifulSoup, page_url: str) -> list[Apartment]:
        apartments = []
        for card in soup.select("article.result-list__listing"):
            try:
                listing_id = card.get("data-id", "")
                link_tag   = card.select_one("a[href*='/expose/']")
                href       = urljoin("https://www.immobilienscout24.de",
                                     link_tag["href"]) if link_tag else page_url

                criteria   = card.select("dl.result-list-entry__primary-criterion dd")
                price_raw  = self.safe_text(criteria[0]) if len(criteria) > 0 else ""
                sqm_raw    = self.safe_text(criteria[1]) if len(criteria) > 1 else ""
                rooms_raw  = self.safe_text(criteria[2]) if len(criteria) > 2 else ""

                title      = self.safe_text(card.select_one(".result-list-entry__brand-title"))
                address    = self.safe_text(card.select_one(".result-list-entry__address"))
                desc       = self.safe_text(card.select_one(".result-list-entry__description"))

                # Floor: "3. OG" / "EG" / "DG"
                floor_m = re.search(r"(\d+)\.\s*OG|EG|DG|KG", address + " " + desc, re.IGNORECASE)
                floor   = floor_m.group(0) if floor_m else None

                full_text     = title + " " + desc
                social_status = detect_social_status(full_text)

                apartments.append(Apartment(
                    id            = self.make_id(listing_id or href[-12:]),
                    source        = self.name,
                    url           = href,
                    title         = title or address or "IS24 Inserat",
                    price         = de_price(price_raw),
                    currency      = "EUR",
                    rooms         = de_rooms(rooms_raw),
                    sqm           = de_sqm(sqm_raw),
                    floor         = floor,
                    address       = address,
                    social_status = social_status,
                    description   = desc[:200] if desc else None,
                ))
            except Exception:
                continue
        return apartments


# ─────────────────────────────────────────────────────────────
# 2. Immowelt
# ─────────────────────────────────────────────────────────────
class ImmoweltScraper(BaseScraper):
    """
    https://www.immowelt.de/liste/wohnungen/mieten
    Card structure:
      <div class="listitem_wrap" data-estateid="12345">
        <a class="listitem" href="/expose/12345">
        <div class="hardfact price"> <strong>850 €</strong> </div>
        <div class="hardfact size">  <strong>65 m²</strong> </div>
        <div class="hardfact rooms"> <strong>2</strong> Zimmer </div>
        <div class="listlocation"> Berliner Str. 10, 80333 München </div>
        <h2 class="listitem_title"> Helle 2-Zimmer-Wohnung </h2>
        <p class="listitem_text"> ... </p>
      </div>
    """

    slug     = "immowelt"
    name     = "Immowelt"
    base_url = "https://www.immowelt.de/liste/berlin/wohnungen/mieten"

    async def listing_urls(self) -> AsyncIterator[str]:
        for pg in range(1, 4):
            yield f"{self.base_url}?sp={pg}"

    def parse_listings(self, soup: BeautifulSoup, page_url: str) -> list[Apartment]:
        apartments = []
        for card in soup.select("div.listitem_wrap"):
            try:
                estate_id = card.get("data-estateid", "")
                link_tag  = card.select_one("a.listitem")
                href      = urljoin("https://www.immowelt.de",
                                    link_tag["href"]) if link_tag else page_url

                price_tag = card.select_one(".hardfact.price strong")
                size_tag  = card.select_one(".hardfact.size strong")
                rooms_tag = card.select_one(".hardfact.rooms strong")
                loc_tag   = card.select_one(".listlocation")
                title_tag = card.select_one("h2.listitem_title")
                desc_tag  = card.select_one("p.listitem_text")

                desc      = self.safe_text(desc_tag)
                title     = self.safe_text(title_tag)
                address   = self.safe_text(loc_tag)

                # Extract district (Stadtteil) from address: "80333 München-Maxvorstadt"
                district_m = re.search(r"\d{5}\s+[\w\s]+-(\w+)", address)
                district   = district_m.group(1) if district_m else None

                full_text     = title + " " + desc
                social_status = detect_social_status(full_text)

                apartments.append(Apartment(
                    id            = self.make_id(estate_id or href[-12:]),
                    source        = self.name,
                    url           = href,
                    title         = title or "Immowelt Inserat",
                    price         = de_price(self.safe_text(price_tag)),
                    currency      = "EUR",
                    rooms         = de_rooms(self.safe_text(rooms_tag)),
                    sqm           = de_sqm(self.safe_text(size_tag)),
                    address       = address,
                    district      = district,
                    social_status = social_status,
                    description   = desc[:200] if desc else None,
                ))
            except Exception:
                continue
        return apartments


# ─────────────────────────────────────────────────────────────
# 3. WG-Gesucht (shared flats + private rooms)
# ─────────────────────────────────────────────────────────────
class WGGesuchtScraper(BaseScraper):
    """
    https://www.wg-gesucht.de/wohnungen-in-Berlin.8.2.1.0.html
    Card structure:
      <div class="wgg_card offer_list_item" data-id="12345">
        <a href="/wohnungen-in-Berlin/12345.html">
        <div class="col-xs-3 text-right">
          <div class="middle"> <b> 850 € </b> </div>
        </div>
        <div class="col-xs-5 middle">
          <span class="wgg_tag"> 65 m² </span>
          <span class="wgg_tag"> 3 Zimmer </span>
        </div>
        <span class="truncate_title"> Helle Altbauwohnung... </span>
        <span class="col-xs-11 flex_space_between">
          <span> Prenzlauer Berg, Berlin </span>
        </span>
      </div>
    """

    slug     = "wg_gesucht"
    name     = "WG-Gesucht"
    base_url = "https://www.wg-gesucht.de/wohnungen-in-Berlin.8.2.1.0.html"

    async def listing_urls(self) -> AsyncIterator[str]:
        for pg in range(0, 3):
            yield f"{self.base_url}?offset={pg * 20}"

    def parse_listings(self, soup: BeautifulSoup, page_url: str) -> list[Apartment]:
        apartments = []
        for card in soup.select("div.wgg_card.offer_list_item"):
            try:
                listing_id = card.get("data-id", "")
                link_tag   = card.select_one("a[href*='/wohnungen']")
                href       = urljoin("https://www.wg-gesucht.de",
                                     link_tag["href"]) if link_tag else page_url

                price_tag = card.select_one(".middle b")
                tags      = card.select(".wgg_tag")
                title_tag = card.select_one(".truncate_title")
                loc_tags  = card.select(".col-xs-11 span")

                price     = de_price(self.safe_text(price_tag))
                sqm       = None
                rooms     = None
                for tag in tags:
                    t = self.safe_text(tag)
                    if "m²" in t or "qm" in t:
                        sqm   = de_sqm(t)
                    elif "zimmer" in t.lower() or "zi" in t.lower():
                        rooms = de_rooms(t)

                loc_text  = " ".join(self.safe_text(l) for l in loc_tags)
                title     = self.safe_text(title_tag)

                apartments.append(Apartment(
                    id            = self.make_id(listing_id or href[-12:]),
                    source        = self.name,
                    url           = href,
                    title         = title or "WG-Gesucht Inserat",
                    price         = price,
                    currency      = "EUR",
                    rooms         = rooms,
                    sqm           = sqm,
                    address       = loc_text,
                    social_status = detect_social_status(title),
                ))
            except Exception:
                continue
        return apartments


# ─────────────────────────────────────────────────────────────
# 4. eBay Kleinanzeigen (Wohnungen zur Miete)
# ─────────────────────────────────────────────────────────────
class EbayKleinanzeigenScraper(BaseScraper):
    """
    https://www.kleinanzeigen.de/s-wohnung-mieten/berlin/c203l3331
    Card structure:
      <article class="aditem" data-adid="12345">
        <a class="ellipsis" href="/s-anzeige/wohnung/12345-...">
        <p class="aditem-main--middle--price-shipping--price"> 850 € </p>
        <p class="aditem-main--middle--description"> 3 Zimmer · 65 m² · 2. OG </p>
        <div class="aditem-main--top--left">
          <p class="aditem-main--top--left--title"> Helle Wohnung ... </p>
        </div>
        <div class="aditem-main--top--right">
          <p> Prenzlauer Berg </p>
          <p> Heute, 10:30 Uhr </p>
        </div>
      </article>
    """

    slug     = "kleinanzeigen"
    name     = "Kleinanzeigen"
    base_url = "https://www.kleinanzeigen.de/s-wohnung-mieten/berlin/c203l3331"

    async def listing_urls(self) -> AsyncIterator[str]:
        for pg in range(1, 4):
            yield f"{self.base_url}/seite:{pg}"

    def parse_listings(self, soup: BeautifulSoup, page_url: str) -> list[Apartment]:
        apartments = []
        for card in soup.select("article.aditem"):
            try:
                ad_id    = card.get("data-adid", "")
                link_tag = card.select_one("a.ellipsis")
                href     = urljoin("https://www.kleinanzeigen.de",
                                   link_tag["href"]) if link_tag else page_url

                price_tag = card.select_one(".aditem-main--middle--price-shipping--price")
                desc_tag  = card.select_one(".aditem-main--middle--description")
                title_tag = card.select_one(".aditem-main--top--left--title")
                loc_tags  = card.select(".aditem-main--top--right p")

                price     = de_price(self.safe_text(price_tag))
                desc_text = self.safe_text(desc_tag)
                title     = self.safe_text(title_tag)

                # Description often has "3 Zimmer · 65 m² · 2. OG"
                parts     = [p.strip() for p in desc_text.split("·")]
                rooms     = None
                sqm       = None
                floor     = None
                for p in parts:
                    if "zimmer" in p.lower() or re.match(r"^\d+\s*(zi|zim)", p, re.I):
                        rooms = de_rooms(p)
                    elif "m²" in p or "qm" in p:
                        sqm   = de_sqm(p)
                    elif re.search(r"OG|EG|DG", p, re.I):
                        floor = p.strip()

                loc_text  = self.safe_text(loc_tags[0]) if loc_tags else None
                published = self.safe_text(loc_tags[1]) if len(loc_tags) > 1 else None

                apartments.append(Apartment(
                    id            = self.make_id(ad_id or href[-12:]),
                    source        = self.name,
                    url           = href,
                    title         = title or "Kleinanzeigen Inserat",
                    price         = price,
                    currency      = "EUR",
                    rooms         = rooms,
                    sqm           = sqm,
                    floor         = floor,
                    address       = loc_text,
                    social_status = detect_social_status(title + " " + desc_text),
                    published_at  = published,
                ))
            except Exception:
                continue
        return apartments


# ─────────────────────────────────────────────────────────────
# 5. Sozialwohnungen / WBS portal (social housing)
# ─────────────────────────────────────────────────────────────
class SozialwohnungenScraper(BaseScraper):
    """
    Example: https://inberlinwohnen.de/wohnungsfinder/
    (Berlin's social housing search — requires WBS)
    Card structure:
      <div class="wohnungsfinder-item">
        <h3 class="wohnungsfinder-item__title"> 3-Zimmer-Wohnung, Prenzlauer Berg </h3>
        <ul class="wohnungsfinder-item__details">
          <li> Kaltmiete: 650,00 € </li>
          <li> Wohnfläche: 78,00 m² </li>
          <li> Zimmer: 3 </li>
          <li> Etage: 3 </li>
          <li> WBS erforderlich </li>
        </ul>
        <a class="wohnungsfinder-item__link" href="/angebot/12345"> Zur Wohnung </a>
      </div>
    """

    slug     = "inberlinwohnen"
    name     = "InBerlinWohnen (WBS)"
    base_url = "https://inberlinwohnen.de/wohnungsfinder/"

    async def listing_urls(self) -> AsyncIterator[str]:
        yield self.base_url

    def parse_listings(self, soup: BeautifulSoup, page_url: str) -> list[Apartment]:
        apartments = []
        for card in soup.select("div.wohnungsfinder-item"):
            try:
                title_tag = card.select_one(".wohnungsfinder-item__title")
                link_tag  = card.select_one("a.wohnungsfinder-item__link")
                details   = card.select(".wohnungsfinder-item__details li")

                href      = urljoin(self.base_url,
                                    link_tag["href"]) if link_tag else page_url
                uid       = href.rstrip("/").split("/")[-1]
                title     = self.safe_text(title_tag)

                price, sqm, rooms, floor = None, None, None, None
                wbs_required = False

                for li in details:
                    t = self.safe_text(li).lower()
                    if "kaltmiete" in t or "miete" in t:
                        price = de_price(t)
                    elif "wohnfläche" in t or "fläche" in t:
                        sqm   = de_sqm(t)
                    elif "zimmer" in t:
                        rooms = de_rooms(t)
                    elif "etage" in t or "og" in t or "eg" in t:
                        floor = re.sub(r"etage[:\s]*", "", t, flags=re.I).strip()
                    if "wbs" in t:
                        wbs_required = True

                social_status = "wbs" if wbs_required else detect_social_status(title)

                apartments.append(Apartment(
                    id            = self.make_id(uid or title[:20]),
                    source        = self.name,
                    url           = href,
                    title         = title or "Sozialwohnung Inserat",
                    price         = price,
                    currency      = "EUR",
                    rooms         = rooms,
                    sqm           = sqm,
                    floor         = floor,
                    social_status = social_status,
                ))
            except Exception:
                continue
        return apartments