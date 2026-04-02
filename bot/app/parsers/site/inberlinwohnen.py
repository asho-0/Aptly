import hashlib
from urllib.parse import urlparse, urlsplit, urlunsplit

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.core.apartment import Apartment
from app.core.enums import SocialStatus
from app.parsers.base.base import BaseScraper
from app.parsers.utils.de_parsing import (
    detect_social_housing_status,
    parse_german_price,
    parse_german_room_count,
    parse_german_sqm,
)

RESULTS_WRAPPER_JS = """
(baseOrigin) => {
    const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim();
    const parseSnapshot = (node) => {
        const raw = node.getAttribute('wire:snapshot');
        if (!raw) return null;
        try {
            return JSON.parse(raw);
        } catch {
            return null;
        }
    };

    const unwrapLivewire = (value) => {
        if (Array.isArray(value)) {
            if (value.length === 2 && value[1] && typeof value[1] === 'object' && value[1].s === 'arr') {
                return unwrapLivewire(value[0]);
            }
            if (value.length > 0) {
                return unwrapLivewire(value[0]);
            }
        }
        return value;
    };

    const listingData = (node) => {
        const snapshot = parseSnapshot(node);
        const item = unwrapLivewire(snapshot?.data?.item);
        return item && typeof item === 'object' ? item : null;
    };

    const wrappers = Array.from(document.querySelectorAll('div[wire\\\\:loading\\\\.remove]'));
    const candidates = wrappers
        .map((wrapper) => ({
            wrapper,
            count: Array.from(wrapper.children).filter((child) => !!listingData(child)).length,
        }))
        .filter((entry) => entry.count > 0)
        .sort((left, right) => right.count - left.count);

    const wrapper = candidates[0]?.wrapper;
    if (!wrapper) {
        return [];
    }

    return Array.from(wrapper.children)
        .map((card, index) => {
            const item = listingData(card);
            if (!item) return null;

            const addressData = unwrapLivewire(item.address) || {};
            const companyData = unwrapLivewire(item.company) || {};
            const rawImage =
                card.querySelector('img[src]')?.getAttribute('src') ||
                card.querySelector('img[data-src]')?.getAttribute('data-src') ||
                card.querySelector('img[data-lazy-src]')?.getAttribute('data-lazy-src') ||
                '';

            const imageUrl = rawImage
                ? new URL(rawImage, baseOrigin).toString()
                : item.imagePath
                  ? new URL(`/img/${String(item.imagePath).replace(/^\\/+/, '')}`, baseOrigin).toString()
                  : '';

            return {
                index,
                textContent: normalize(card.textContent),
                lines: Array.from(
                    new Set(
                        (card.textContent || '')
                            .split(/\\n+/)
                            .map((line) => normalize(line))
                            .filter(Boolean)
                    )
                ),
                item,
                addressData,
                companyData,
                imageUrl,
            };
        })
        .filter(Boolean);
}
"""


def _normalize_text(value: object) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _contains_zip_code(value: str) -> bool:
    digits = 0
    for char in value:
        if char.isdigit():
            digits += 1
            if digits >= 5:
                return True
        else:
            digits = 0
    return False


def _extract_digit_runs(value: str, min_length: int = 1) -> list[str]:
    current = []
    runs: list[str] = []
    for char in value:
        if char.isdigit():
            current.append(char)
            continue
        if len(current) >= min_length:
            runs.append("".join(current))
        current = []
    if len(current) >= min_length:
        runs.append("".join(current))
    return runs


def _parse_numeric(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    text = _normalize_text(value)
    if not text:
        return None

    clean = text.replace("€", "").replace("EUR", "").strip()
    if "," in clean and "." in clean:
        clean = clean.replace(".", "").replace(",", ".")
    elif "," in clean:
        clean = clean.replace(",", ".")

    filtered = "".join(char for char in clean if char.isdigit() or char == ".")
    if not filtered:
        return None

    try:
        return float(filtered)
    except ValueError:
        return None


def _canonical_listing_url(url: str) -> str:
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower()
    return urlunsplit(
        (
            parsed.scheme.lower(),
            hostname + (f":{parsed.port}" if parsed.port else ""),
            parsed.path,
            "",
            "",
        )
    )


def _format_address(street: str, number: str, zip_code: str) -> str:
    left = _normalize_text(
        " ".join(part for part in [street, number] if _normalize_text(part))
    )
    right = _normalize_text(zip_code)
    if left and right:
        return f"{left}, {right}"
    return left or right


def _format_floor(level: object, total: object) -> str | None:
    level_text = _normalize_text(level)
    total_text = _normalize_text(total)
    if level_text and total_text:
        return f"{level_text}/{total_text}"
    if level_text:
        return level_text
    return total_text or None


def _extract_labeled_value(lines: list[object], label: str) -> str:
    normalized_label = label.lower().rstrip(":")
    cleaned_lines = [_normalize_text(line) for line in lines if _normalize_text(line)]

    for index, line in enumerate(cleaned_lines):
        lowered = line.lower().rstrip(":")
        if lowered == normalized_label:
            if index + 1 < len(cleaned_lines):
                return cleaned_lines[index + 1]
            return ""
        if lowered.startswith(f"{normalized_label}:"):
            return _normalize_text(line.split(":", 1)[1])
    return ""


def _normalize_company_name(raw_name: str) -> str:
    text = _normalize_text(raw_name).lower()
    mapping = {
        "berlinovo": "Berlinovo",
        "degewo": "Degewo",
        "gesobau": "GESOBAU",
        "gewobag": "Gewobag",
        "howoge": "Howoge",
        "stadt und land": "Stadt und Land",
        "wbm": "WBM",
    }
    for needle, label in mapping.items():
        if needle in text:
            return label
    return _normalize_text(raw_name)


def _resolve_source_name(apartment_url: str, company_name: str = "") -> str:
    if company_name:
        normalized = _normalize_company_name(company_name)
        if normalized:
            return normalized

    hostname = (urlparse(apartment_url).hostname or "").replace("www.", "")
    mapping = {
        "berlinovo.de": "Berlinovo",
        "degewo.de": "Degewo",
        "gesobau.de": "GESOBAU",
        "gewobag.de": "Gewobag",
        "howoge.de": "Howoge",
        "stadtundland.de": "Stadt und Land",
        "wbm.de": "WBM",
    }
    for domain, label in mapping.items():
        if hostname == domain or hostname.endswith(f".{domain}"):
            return label
    return "inberlinwohnen.de"


def _extract_social_status(
    title: str, details_text: str, wbs_text: str = ""
) -> SocialStatus:
    explicit = wbs_text.lower()
    if "nicht erforderlich" in explicit:
        return SocialStatus.MARKET
    if "erforderlich" in explicit:
        return SocialStatus.WBS

    probe = f"{title} {details_text}".lower()
    if "wbs nicht erforderlich" in probe:
        return SocialStatus.MARKET
    if "wbs erforderlich" in probe:
        return SocialStatus.WBS
    return detect_social_housing_status(probe)


def _fallback_parse_raw_card(raw_card: dict[str, object], make_id) -> Apartment | None:
    title = _normalize_text(raw_card.get("title"))
    address = _normalize_text(raw_card.get("address"))
    url = _normalize_text(raw_card.get("url"))
    price_text = _normalize_text(raw_card.get("priceText"))
    area_text = _normalize_text(raw_card.get("areaText"))
    room_text = _normalize_text(raw_card.get("roomText"))
    detail_text = _normalize_text(raw_card.get("detailText"))
    image_url = _normalize_text(raw_card.get("imageUrl")) or None
    external_id = _normalize_text(raw_card.get("externalId"))

    if not external_id:
        if url:
            external_id = hashlib.sha1(
                _canonical_listing_url(url).encode("utf-8")
            ).hexdigest()[:16]
        else:
            return None

    if len(title) < 3 or not _contains_zip_code(address) or not url.startswith("http"):
        return None

    price = parse_german_price(price_text)
    sqm = parse_german_sqm(area_text)
    rooms = parse_german_room_count(room_text)
    if price is None or sqm is None or rooms is None:
        return None

    district = ""
    parts = [part.strip() for part in address.split(",") if part.strip()]
    if len(parts) >= 2:
        district = parts[-1]
        address = ", ".join(parts[:-1])

    social_status = _extract_social_status(
        title,
        detail_text,
        _normalize_text(raw_card.get("wbs")),
    )

    return Apartment(
        id=make_id(external_id),
        source=_resolve_source_name(url),
        url=url,
        title=title,
        price=price,
        cold_rent=price,
        extra_costs=None,
        rooms=rooms,
        sqm=sqm,
        floor=None,
        address=address,
        district=district,
        social_status=social_status,
        description=detail_text,
        image_url=image_url,
    )


def _parse_snapshot_card(raw_card: dict[str, object], make_id) -> Apartment | None:
    item = raw_card.get("item")
    address_data = raw_card.get("addressData")
    company_data = raw_card.get("companyData")

    if not isinstance(item, dict):
        return None

    url = _normalize_text(item.get("deeplink"))
    canonical_url = _canonical_listing_url(url) if url.startswith("http") else ""
    external_id = (
        hashlib.sha1(canonical_url.encode("utf-8")).hexdigest()[:16]
        if canonical_url
        else ""
    )
    if not external_id:
        item_id = _normalize_text(item.get("id"))
        external_id = item_id or ""
    if not external_id:
        return None

    title = _normalize_text(item.get("title"))
    if len(title) < 3:
        return None

    street = number = zip_code = district = ""
    if isinstance(address_data, dict):
        street = _normalize_text(address_data.get("street"))
        number = _normalize_text(address_data.get("number"))
        zip_code = _normalize_text(address_data.get("zipCode"))
        district = _normalize_text(address_data.get("district"))

    address = _format_address(street, number, zip_code)
    if not _contains_zip_code(address):
        for line in raw_card.get("lines", []):
            text = _normalize_text(line)
            if _contains_zip_code(text):
                address = text
                break
    if not _contains_zip_code(address):
        return None

    rooms_text = f"{_normalize_text(item.get('rooms'))} Zimmer"
    area_text = f"{_normalize_text(item.get('area'))} m²"
    rooms = parse_german_room_count(rooms_text)
    sqm = parse_german_sqm(area_text)
    if rooms is None or sqm is None:
        return None

    lines = raw_card.get("lines", [])
    cold_rent = _parse_numeric(
        _extract_labeled_value(lines, "Kaltmiete") or item.get("rentNet")
    )
    extra_costs = _parse_numeric(
        _extract_labeled_value(lines, "Nebenkosten") or item.get("extraCosts")
    )
    total_rent = _parse_numeric(
        _extract_labeled_value(lines, "Gesamtmiete") or item.get("rentGross")
    )
    if total_rent is None:
        total_rent = cold_rent
        if total_rent is not None and extra_costs is not None:
            total_rent += extra_costs
    if total_rent is None:
        return None

    company_name = (
        _normalize_text(company_data.get("name"))
        if isinstance(company_data, dict)
        else ""
    )
    image_url = _normalize_text(raw_card.get("imageUrl")) or None
    floor = _extract_labeled_value(lines, "Etage") or _format_floor(
        item.get("level"), item.get("levelsTotal")
    )
    details_text = _normalize_text(raw_card.get("textContent"))
    wbs_text = _extract_labeled_value(lines, "WBS")
    social_status = _extract_social_status(title, details_text, wbs_text)

    published_at = _normalize_text(item.get("createdAt")) or None

    return Apartment(
        id=make_id(external_id),
        source=_resolve_source_name(url, company_name),
        url=url,
        title=title,
        price=total_rent,
        cold_rent=cold_rent,
        extra_costs=extra_costs,
        rooms=rooms,
        sqm=sqm,
        floor=floor,
        address=address,
        district=district,
        social_status=social_status,
        description=details_text,
        image_url=image_url,
        published_at=published_at,
    )


def _parse_raw_card(raw_card: dict[str, object], make_id) -> Apartment | None:
    if isinstance(raw_card.get("item"), dict):
        return _parse_snapshot_card(raw_card, make_id)
    return _fallback_parse_raw_card(raw_card, make_id)


async def _get_page(scraper: "InBerlinWohnenScraper") -> Page:
    if scraper._context is None:
        scraper._playwright = await async_playwright().start()
        scraper._browser = await scraper._playwright.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        scraper._context = await scraper._browser.new_context(
            locale="de-DE",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36",
        )
    return await scraper._context.new_page()


async def _accept_cookies(page: Page) -> None:
    button = page.locator("#accept-selected-cookies, #accept-all-cookies").first
    if await button.count():
        try:
            await button.click(timeout=3000)
            await page.wait_for_timeout(300)
        except Exception:
            return


async def _extract_cards(page: Page, base_origin: str) -> list[dict[str, object]]:
    return await page.evaluate(RESULTS_WRAPPER_JS, base_origin)


async def _wait_for_results(page: Page, base_origin: str) -> None:
    await page.wait_for_selector(".pagination", timeout=60000)
    for _ in range(80):
        cards = await _extract_cards(page, base_origin)
        if cards:
            await page.wait_for_timeout(200)
            return
        await page.wait_for_timeout(250)
    raise TimeoutError("Timed out waiting for listing cards")


async def _go_to_next_page(page: Page, current_page: int, base_origin: str) -> bool:
    pagination_text = page.locator(".pagination p").first
    before = _normalize_text(
        await pagination_text.text_content() if await pagination_text.count() else ""
    )
    next_button = page.locator(
        "button[wire\\:click=\"$dispatch('nextPage')\"], .pagination button:has-text('Vor')"
    ).first
    if not await next_button.count():
        return False
    if await next_button.is_disabled():
        return False

    await next_button.click()

    for _ in range(40):
        await page.wait_for_timeout(250)
        cards = await _extract_cards(page, base_origin)
        after = _normalize_text(
            await pagination_text.text_content()
            if await pagination_text.count()
            else ""
        )
        if cards and before and after and before != after:
            await page.wait_for_timeout(200)
            return True

        target_button = page.locator(
            f"button[wire\\:click=\"$dispatch('gotoPage', {{page: {current_page + 1}}})\"]"
        ).first
        if await target_button.count():
            try:
                if await target_button.is_disabled() and cards:
                    return True
            except Exception:
                pass

    return False


class InBerlinWohnenScraper(BaseScraper):
    slug = "inberlinwohnen"
    name = "inberlinwohnen.de"
    base_url = (
        "https://www.inberlinwohnen.de/wohnungsfinder?q="
        "eyJpdiI6ImNnTHZKU0FJYmRDVXBMTjI3a3Nsdnc9PSIsInZhbHVlIjoiZDdaY0xBNDJMd01panFOZHNSNi9kaXlHMjgwQUx4SUlKNXM3NzBYUWZCcDJpVVk2eVFJTkpKV1FIOUpMbVRqWm9IVk1XVnlMbnhCRmhsZU9XZ1ZwVEd1SmNhMFJRcENYMHlXK25EMXkrUmthSUpsUk42MkNiaUJTWVh2SVlMUWovM1IwbHV4TWU2Sm9tazI5RHpvNnBpUlhYbGhlaUFwVExBeXgxMEJUS2tzRWJCbEMyTFZjdGkrdUN0amlDTGdvL2E1RHJnODNGdDFRRzE2SHBPcXp3enZuQmdxSWhHWWYxYkZYMWlXTWxTT2hkTWtnNWo5Q1d4aHl3c3kyRTlFRy84T1lEY2hDMllMQ3BlSG9TRzZ4NE83bDRTREo5Wk82M25wQkROdUxBRHdqdjlQMHpaTmsvQzljVHJxZmcyNTg1UU1pTFVUVmEwZWI5Njl0VEptZTMxaG5rRGtCWDF3T0pqVUtpcllXa09HeW1JbWFLYU8welFnQWZESENjelR3OU8vZTZhUkw5YmNHaWN5V2t5dklCUT09IiwibWFjIjoiMDM4YWJjNjBiZGFiNzZmYjRmMDI5NThkYzA1N2I4YWEwMzBkYjQ2MDdmZWU1MDUxZWI3YTI4YmRhMTRkMzU2YyIsInRhZyI6IiJ9"
    )

    def __init__(self) -> None:
        super().__init__()
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def _parse_raw_card(self, raw_card: dict[str, object]) -> Apartment | None:
        return _parse_raw_card(raw_card, self.make_id)

    async def iter_listings(self):
        page = await _get_page(self)
        await page.goto(self.base_url, wait_until="domcontentloaded", timeout=60000)
        await _accept_cookies(page)
        await _wait_for_results(page, self.domain)

        seen_ids: set[str] = set()
        previous_fingerprint = ""

        for page_number in range(1, self.MAX_PAGES + 1):
            raw_cards = await _extract_cards(page, self.domain)
            if not raw_cards:
                break

            fingerprint_parts: list[str] = []
            for raw_card in raw_cards[:3]:
                item = raw_card.get("item")
                if isinstance(item, dict):
                    fingerprint_parts.append(
                        _normalize_text(item.get("deeplink") or item.get("id"))
                    )
            current_fingerprint = "|".join(part for part in fingerprint_parts if part)
            if current_fingerprint and current_fingerprint == previous_fingerprint:
                break
            previous_fingerprint = current_fingerprint

            for raw_card in raw_cards:
                apartment = self._parse_raw_card(raw_card)
                if apartment is None or apartment.id in seen_ids:
                    continue
                seen_ids.add(apartment.id)
                yield apartment

            if not await _go_to_next_page(page, page_number, self.domain):
                break

    async def fetch_all(self) -> list[Apartment]:
        apartments: list[Apartment] = []
        async for apartment in self.iter_listings():
            apartments.append(apartment)
        return apartments

    async def close_session(self) -> None:
        if self._context is not None:
            await self._context.close()
            self._context = None
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
