import logging
import typing as t
from dataclasses import dataclass, field
from urllib.parse import quote

from app.core.enums import SocialStatus
from app.telegram.interface.labels import FILTER_LABELS, APARTMENT_LABELS

logger = logging.getLogger(__name__)

SPECIAL_CONTENT_MARKERS = (
    "student",
    "studenten",
    "studentisch",
    "senior",
    "senioren",
    "55 jahre",
    "55+",
    "ab 55",
    "wohnen ab 55",
)


@dataclass(slots=True)
class ProcessResult:
    uid: str
    listing_db_id: t.Optional[int]
    is_new_in_db: bool
    passed_filter: bool
    notified: bool


@dataclass(slots=True)
class ApartmentFilter:
    min_rooms: int | None = None
    max_rooms: int | None = None
    min_sqm: float | None = None
    max_sqm: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    social_status: SocialStatus = SocialStatus.ANY

    def is_complete(self) -> bool:
        return (
            self.min_rooms is not None
            and self.max_rooms is not None
            and self.min_sqm is not None
            and self.max_sqm is not None
            and self.min_price is not None
            and self.max_price is not None
        )

    def summary(self, lang: str = "en", show_special_listings: bool = False) -> str:
        labels = FILTER_LABELS.get(lang, FILTER_LABELS["en"])
        placeholder = labels["none"]

        def _range(low: float | None, high: float | None, unit: str = "") -> str:
            low_str = str(low) if low is not None else placeholder
            high_str = str(high) if high is not None else placeholder
            suffix = f" {unit}" if unit else ""
            return f"{low_str}-{high_str}{suffix}"

        lines = [labels["header"]]
        lines.append(f"{labels['rooms']}:   {_range(self.min_rooms, self.max_rooms)}")
        lines.append(
            f"{labels['area']}:    {_range(self.min_sqm, self.max_sqm, labels['sqm_unit'])}"
        )
        lines.append(
            f"{labels['price']}:   {_range(self.min_price, self.max_price, labels['price_unit'])}"
        )
        lines.append(f"{labels['status']}:  {self.social_status}")
        lines.append(
            f"{labels['special_content']}:  {labels['special_on'] if show_special_listings else labels['special_off']}"
        )
        return "\n".join(lines)


@dataclass(slots=True)
class Apartment:
    id: str
    source: str
    url: str
    title: str
    price: float | None = None
    cold_rent: float | None = None
    extra_costs: float | None = None
    currency: str = "EUR"
    rooms: int | None = None
    sqm: float | None = None
    floor: str | None = None
    address: str | None = None
    district: str | None = None
    social_status: SocialStatus = SocialStatus.ANY
    description: str | None = None
    image_url: str | None = None
    published_at: str | None = None
    _special_content_cache: bool | None = field(
        init=False, default=None, repr=False, compare=False
    )
    _title_lower_cache: str | None = field(
        init=False, default=None, repr=False, compare=False
    )
    _is_wbs_in_title_cache: bool | None = field(
        init=False, default=None, repr=False, compare=False
    )

    def _title_lower(self) -> str:
        if self._title_lower_cache is None:
            self._title_lower_cache = self.title.lower()
        return self._title_lower_cache

    def is_special_content(self) -> bool:
        if self._special_content_cache is None:
            probe = " ".join(
                part.lower() for part in (self.title, self.description) if part
            )
            self._special_content_cache = any(
                marker in probe for marker in SPECIAL_CONTENT_MARKERS
            )
        return self._special_content_cache

    def _is_wbs_in_title(self) -> bool:
        if self._is_wbs_in_title_cache is None:
            title_lower = self._title_lower()
            self._is_wbs_in_title_cache = any(
                word in title_lower
                for word in ("wbs", "berechtigungsschein", "stypendium")
            )
        return self._is_wbs_in_title_cache

    def matches(
        self, apartment_filter: ApartmentFilter, show_special_listings: bool = False
    ) -> bool:
        if not apartment_filter.is_complete():
            return False

        if not show_special_listings and self.is_special_content():
            return False

        if self.price is None:
            return False

        min_p = apartment_filter.min_price if apartment_filter.min_price is not None else 0
        max_p = (
            apartment_filter.max_price if apartment_filter.max_price is not None else 999999
        )

        if not (min_p <= self.price <= max_p):
            return False

        if self.rooms is not None:
            min_r = apartment_filter.min_rooms if apartment_filter.min_rooms is not None else 0
            max_r = apartment_filter.max_rooms if apartment_filter.max_rooms is not None else 99
            if not (min_r <= self.rooms <= max_r):
                return False

        if self.sqm is not None:
            min_s = apartment_filter.min_sqm if apartment_filter.min_sqm is not None else 0
            max_s = apartment_filter.max_sqm if apartment_filter.max_sqm is not None else 999
            if not (min_s <= self.sqm <= max_s):
                return False

        is_actually_wbs = (
            self.social_status == SocialStatus.WBS or self._is_wbs_in_title()
        )

        if apartment_filter.social_status == SocialStatus.MARKET and is_actually_wbs:
            return False
        if apartment_filter.social_status == SocialStatus.WBS and not is_actually_wbs:
            return False

        return True

    def to_telegram_message(self, lang: str = "en") -> str:
        lb = APARTMENT_LABELS.get(lang, APARTMENT_LABELS["en"])

        def fmt_price(v: float) -> str:
            return f"{v:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

        lines: list[str] = []

        if self.source:
            header = f"🏠 <b>{self.source}</b> | {self.title}"
        else:
            header = f"🏠 {self.title}"
        lines.append(header)
        lines.append("")

        address_text = (self.address or "").strip()
        district_text = (self.district or "").strip()
        location_parts: list[str] = []
        if address_text:
            location_parts.append(address_text)
        if district_text and district_text.lower() not in address_text.lower():
            location_parts.append(district_text)
        if location_parts:
            location = ", ".join(location_parts)
            maps_url = (
                f"https://www.google.com/maps/search/?api=1&query={quote(location)}"
            )
            lines.append(
                f"{lb['address']} <a href=\"{maps_url}\">{address_text or location}</a>"
            )
        if district_text:
            lines.append(f"{lb['district']} {district_text}")

        if self.rooms is not None:
            lines.append(f"{lb['rooms']} {self.rooms:g}")
        if self.sqm is not None:
            lines.append(f"{lb['area']} {self.sqm:.2f} {lb['area_unit']}")
        if self.cold_rent is not None:
            lines.append(f"{lb['cold_rent']} {fmt_price(self.cold_rent)}")
        if self.extra_costs is not None:
            lines.append(f"{lb['extra_costs']} {fmt_price(self.extra_costs)}")
        if self.price is not None:
            lines.append(f"{lb['total_rent']} {fmt_price(self.price)}")

        if self.social_status == SocialStatus.WBS:
            wbs_val = lb["wbs_yes"]
        elif self.social_status in (SocialStatus.ANY, SocialStatus.MARKET):
            wbs_val = lb["wbs_no"]
        else:
            wbs_val = str(self.social_status)
        lines.append(f"{lb['wbs_label']} {wbs_val}")

        if self.floor:
            lines.append(f"{lb['floor']} {self.floor}")
        return "\n".join(lines)
