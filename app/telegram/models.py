# ============================================================
# models.py — Data models
# ============================================================

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Apartment:
    """Normalised apartment listing scraped from any source."""

    # ── Identity ──────────────────────────────────────────────
    id:            str            # unique key = source_slug + ":" + listing_id
    source:        str            # human-readable site name
    url:           str            # direct link to the announcement

    # ── Core fields ──────────────────────────────────────────
    title:         str
    price:         Optional[float] = None   # monthly rent / asking price
    currency:      str             = "USD"
    rooms:         Optional[int]   = None
    sqm:           Optional[float] = None
    floor:         Optional[str]   = None   # e.g. "3/9"
    address:       Optional[str]   = None
    district:      Optional[str]   = None
    social_status: str             = "market"  # "market"|"subsidy"|"social_housing"|"unknown"
    description:   Optional[str]   = None
    image_url:     Optional[str]   = None
    published_at:  Optional[str]   = None   # raw string from site

    # ── Extra info bag (site-specific extras) ─────────────────
    extras: dict = field(default_factory=dict)

    def matches(self, f) -> bool:  # f: ApartmentFilter
        """Return True if this listing satisfies every active filter."""
        if f.min_rooms  is not None and self.rooms is not None and self.rooms  < f.min_rooms:  return False
        if f.max_rooms  is not None and self.rooms is not None and self.rooms  > f.max_rooms:  return False
        if f.min_sqm    is not None and self.sqm   is not None and self.sqm    < f.min_sqm:    return False
        if f.max_sqm    is not None and self.sqm   is not None and self.sqm    > f.max_sqm:    return False
        if f.min_price  is not None and self.price is not None and self.price  < f.min_price:  return False
        if f.max_price  is not None and self.price is not None and self.price  > f.max_price:  return False
        if f.social_status != "any" and self.social_status != "unknown":
            if self.social_status != f.social_status:
                return False
        title_lower = self.title.lower()
        desc_lower  = (self.description or "").lower()
        text        = title_lower + " " + desc_lower
        if f.exclude_keywords and any(kw.lower() in text for kw in f.exclude_keywords):
            return False
        if f.include_keywords and not any(kw.lower() in text for kw in f.include_keywords):
            return False
        return True

    def to_telegram_message(self) -> str:
        """Format a pretty Telegram HTML message."""
        lines = [
            f"🏠 <b>{self.title}</b>",
            f"🌐 <i>{self.source}</i>",
            "",
        ]
        if self.price is not None:
            lines.append(f"💰 <b>Price:</b> {self.price:,.0f} {self.currency}")
        if self.rooms is not None:
            lines.append(f"🚪 <b>Rooms:</b> {self.rooms}")
        if self.sqm is not None:
            lines.append(f"📐 <b>Area:</b> {self.sqm} m²")
        if self.floor:
            lines.append(f"🏢 <b>Floor:</b> {self.floor}")
        if self.address or self.district:
            loc = ", ".join(filter(None, [self.district, self.address]))
            lines.append(f"📍 <b>Location:</b> {loc}")

        badge = {
            "market":        "🏦 Market price",
            "subsidy":       "💶 Subsidised",
            "social_housing":"🏛 Social housing",
            "unknown":       "❓ Unknown",
        }.get(self.social_status, self.social_status)
        lines.append(f"📋 <b>Social status:</b> {badge}")

        if self.published_at:
            lines.append(f"📅 <b>Published:</b> {self.published_at}")

        lines += ["", f'🔗 <a href="{self.url}">View announcement</a>']
        return "\n".join(lines)