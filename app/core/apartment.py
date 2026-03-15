from dataclasses import dataclass

from app.core.base_apartment import ApartmentBase, ApartmentFilterBase
from app.core.enums import SocialStatus
from app.labels import FILTER_LABELS, APARTMENT_LABELS


@dataclass
class ApartmentFilter(ApartmentFilterBase):
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
class Apartment(ApartmentBase):
    cold_rent: float | None = None
    extra_costs: float | None = None

    def matches(self, apartment_filter: ApartmentFilterBase) -> bool:
        if apartment_filter.min_rooms is not None and self.rooms is not None:
            if self.rooms < apartment_filter.min_rooms:
                return False
        if apartment_filter.max_rooms is not None and self.rooms is not None:
            if self.rooms > apartment_filter.max_rooms:
                return False
        if apartment_filter.min_sqm is not None and self.sqm is not None:
            if self.sqm < apartment_filter.min_sqm:
                return False
        if apartment_filter.max_sqm is not None and self.sqm is not None:
            if self.sqm > apartment_filter.max_sqm:
                return False
        if apartment_filter.min_price is not None and self.price is not None:
            if self.price < apartment_filter.min_price:
                return False
        if apartment_filter.max_price is not None and self.price is not None:
            if self.price > apartment_filter.max_price:
                return False
        if apartment_filter.social_status == SocialStatus.WBS:
            if self.social_status != SocialStatus.WBS:
                return False
        return True

    def to_telegram_message(self) -> str:
        from app.config import settings

        lb = APARTMENT_LABELS.get(settings.BOT_LANGUAGE, APARTMENT_LABELS["en"])

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
