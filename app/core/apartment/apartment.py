import logging
import typing as t
from dataclasses import dataclass

from app.core.enums import SocialStatus
from app.telegram.interface.labels import FILTER_LABELS, APARTMENT_LABELS

logger = logging.getLogger(__name__)


@dataclass
class ProcessResult:
    uid: str
    listing_db_id: t.Optional[int]
    is_new_in_db: bool
    passed_filter: bool
    notified: bool


@dataclass
class ApartmentFilter:
    min_rooms: int | None = None
    max_rooms: int | None = None
    min_sqm: float | None = None
    max_sqm: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    social_status: SocialStatus = SocialStatus.ANY

    def is_complete(self) -> bool:
        return all(
            [
                self.min_rooms is not None,
                self.max_rooms is not None,
                self.min_sqm is not None,
                self.max_sqm is not None,
                self.min_price is not None,
                self.max_price is not None,
            ]
        )

    def summary(self, lang: str = "en") -> str:
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
        return "\n".join(lines)


@dataclass
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

    def matches(self, apartment_filter: ApartmentFilter) -> bool:
        if not apartment_filter.is_complete():
            return False

        if self.price is None:
            return False

        min_p = (
            apartment_filter.min_price if apartment_filter.min_price is not None else 0
        )
        max_p = (
            apartment_filter.max_price
            if apartment_filter.max_price is not None
            else 999999
        )

        if not (min_p <= self.price <= max_p):
            return False

        if self.rooms is not None:
            min_r = (
                apartment_filter.min_rooms
                if apartment_filter.min_rooms is not None
                else 0
            )
            max_r = (
                apartment_filter.max_rooms
                if apartment_filter.max_rooms is not None
                else 99
            )
            if not (min_r <= self.rooms <= max_r):
                return False

        if self.sqm is not None:
            min_s = (
                apartment_filter.min_sqm if apartment_filter.min_sqm is not None else 0
            )
            max_s = (
                apartment_filter.max_sqm
                if apartment_filter.max_sqm is not None
                else 999
            )
            if not (min_s <= self.sqm <= max_s):
                return False

        title_lower = self.title.lower()
        is_wbs_in_title = any(
            word in title_lower for word in ["wbs", "berechtigungsschein", "stypendium"]
        )
        is_actually_wbs = self.social_status == SocialStatus.WBS or is_wbs_in_title

        if apartment_filter.social_status == SocialStatus.MARKET and is_actually_wbs:
            return False
        if apartment_filter.social_status == SocialStatus.WBS and not is_actually_wbs:
            return False

        return True

    def to_telegram_message(self, lang: str = "en") -> str:
        lb = APARTMENT_LABELS.get(lang, APARTMENT_LABELS["en"])

        def fmt_price(v: float) -> str:
            return f"{v:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")

        blocks: list[str] = []

        header = f"🏠 {self.title}"
        if self.source:
            header += f"  |  {self.source}"
        blocks.append(header)

        if self.address or self.district:
            location = ", ".join(p for p in [self.address, self.district] if p)
            blocks.append(f"{lb['address']}\n{location}")

        if self.rooms is not None:
            blocks.append(f"{lb['rooms']}\n{self.rooms:g}")
        if self.sqm is not None:
            blocks.append(f"{lb['area']}\n{self.sqm:.2f} {lb['area_unit']}")
        if self.cold_rent is not None:
            blocks.append(f"{lb['cold_rent']}\n{fmt_price(self.cold_rent)}")
        if self.extra_costs is not None:
            blocks.append(f"{lb['extra_costs']}\n{fmt_price(self.extra_costs)}")
        if self.price is not None:
            blocks.append(f"{lb['total_rent']}\n{fmt_price(self.price)}")

        if self.social_status == SocialStatus.WBS:
            wbs_val = lb["wbs_yes"]
        elif self.social_status in (SocialStatus.ANY, SocialStatus.MARKET):
            wbs_val = lb["wbs_no"]
        else:
            wbs_val = str(self.social_status)
        blocks.append(f"{lb['wbs_label']}\n{wbs_val}")

        if self.floor:
            blocks.append(f"{lb['floor']}\n{self.floor}")
        if self.published_at:
            blocks.append(f"{lb['published']}\n{self.published_at}")

        blocks.append(f"🔗 {self.url}")

        return "\n\n".join(blocks)
