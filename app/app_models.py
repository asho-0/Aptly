# ============================================================
# app_models.py — Application-layer models (non-ORM)
# ============================================================

from dataclasses import dataclass, field
from typing import Optional


# Social status labels — values come from German sites, labels are translated
_STATUS_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "market":        "🏦 Market price",
        "wbs":           "📄 WBS required (social)",
        "sozialwohnung": "🏛 Social housing",
        "staffelmiete":  "📈 Graduated rent",
        "unknown":       "❓ Unknown",
    },
    "ru": {
        "market":        "🏦 Рыночная цена",
        "wbs":           "📄 WBS (соц. жильё)",
        "sozialwohnung": "🏛 Социальное жильё",
        "staffelmiete":  "📈 Ступенчатая аренда",
        "unknown":       "❓ Неизвестно",
    },
}

_FILTER_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "header":    "📊 <b>Active filters:</b>",
        "rooms":     "🚪 Rooms",
        "area":      "📐 Area",
        "price":     "💰 Price",
        "status":    "📋 Status",
        "includes":  "✅ Includes",
        "excludes":  "❌ Excludes",
        "any":       "any",
        "sqm_unit":  "m²",
        "price_unit":"€/mo",
        "none":      "–",
    },
    "ru": {
        "header":    "📊 <b>Активные фильтры:</b>",
        "rooms":     "🚪 Комнаты",
        "area":      "📐 Площадь",
        "price":     "💰 Цена",
        "status":    "📋 Статус",
        "includes":  "✅ Включить",
        "excludes":  "❌ Исключить",
        "any":       "любой",
        "sqm_unit":  "м²",
        "price_unit":"€/мес",
        "none":      "–",
    },
}

_APARTMENT_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "price":     "💰 <b>Rent:</b>",
        "rooms":     "🚪 <b>Rooms:</b>",
        "area":      "📐 <b>Area:</b>",
        "floor":     "🏢 <b>Floor:</b>",
        "location":  "📍 <b>Location:</b>",
        "status":    "📋 <b>Status:</b>",
        "published": "📅 <b>Published:</b>",
        "link":      "View listing",
        "price_unit":"€/mo",
        "area_unit": "m²",
    },
    "ru": {
        "price":     "💰 <b>Аренда:</b>",
        "rooms":     "🚪 <b>Комнаты:</b>",
        "area":      "📐 <b>Площадь:</b>",
        "floor":     "🏢 <b>Этаж:</b>",
        "location":  "📍 <b>Адрес:</b>",
        "status":    "📋 <b>Статус:</b>",
        "published": "📅 <b>Опубликовано:</b>",
        "link":      "Открыть объявление",
        "price_unit":"€/мес",
        "area_unit": "м²",
    },
}


@dataclass
class ApartmentFilter:
    min_rooms:        Optional[int]   = None
    max_rooms:        Optional[int]   = None
    min_sqm:          Optional[float] = None
    max_sqm:          Optional[float] = None
    min_price:        Optional[float] = None
    max_price:        Optional[float] = None
    # Domain values stay in German — they come directly from the scraped sites
    social_status:    str             = "any"
    include_keywords: list[str]       = field(default_factory=list)
    exclude_keywords: list[str]       = field(default_factory=lambda: [
        "gewerbe", "büro", "garage", "lager", "praxis"
    ])

    def summary(self, lang: str = "en") -> str:
        """Render a human-readable filter summary in the given UI language."""
        lb   = _FILTER_LABELS.get(lang, _FILTER_LABELS["en"])
        none = lb["none"]

        def _range(lo, hi, unit: str = "") -> str:
            a = str(lo) if lo is not None else none
            b = str(hi) if hi is not None else none
            suffix = f" {unit}" if unit else ""
            return f"{a} – {b}{suffix}"

        lines = [lb["header"]]
        lines.append(f"{lb['rooms']}:   {_range(self.min_rooms, self.max_rooms)}")
        lines.append(f"{lb['area']}:    {_range(self.min_sqm,   self.max_sqm,   lb['sqm_unit'])}")
        lines.append(f"{lb['price']}:   {_range(self.min_price, self.max_price, lb['price_unit'])}")
        lines.append(f"{lb['status']}:  {self.social_status}")
        if self.include_keywords:
            lines.append(f"{lb['includes']}: {', '.join(self.include_keywords)}")
        if self.exclude_keywords:
            lines.append(f"{lb['excludes']}: {', '.join(self.exclude_keywords)}")
        return "\n".join(lines)

    def matches(self, f: "ApartmentFilter") -> bool:
        if f.min_rooms  is not None and self.rooms is not None and self.rooms  < f.min_rooms:  return False  # type: ignore[attr-defined]
        if f.max_rooms  is not None and self.rooms is not None and self.rooms  > f.max_rooms:  return False  # type: ignore[attr-defined]
        if f.min_sqm    is not None and self.sqm   is not None and self.sqm    < f.min_sqm:    return False  # type: ignore[attr-defined]
        if f.max_sqm    is not None and self.sqm   is not None and self.sqm    > f.max_sqm:    return False  # type: ignore[attr-defined]
        if f.min_price  is not None and self.price is not None and self.price  < f.min_price:  return False  # type: ignore[attr-defined]
        if f.max_price  is not None and self.price is not None and self.price  > f.max_price:  return False  # type: ignore[attr-defined]
        if f.social_status != "any" and self.social_status != "unknown":                                     # type: ignore[attr-defined]
            if self.social_status != f.social_status:                          return False                  # type: ignore[attr-defined]
        text = (self.title + " " + (self.description or "")).lower()                                         # type: ignore[attr-defined]
        if f.exclude_keywords and any(kw.lower() in text for kw in f.exclude_keywords): return False
        if f.include_keywords and not any(kw.lower() in text for kw in f.include_keywords): return False
        return True


@dataclass
class Apartment:
    id:            str
    source:        str
    url:           str
    title:         str
    price:         Optional[float] = None
    currency:      str             = "EUR"
    rooms:         Optional[int]   = None
    sqm:           Optional[float] = None
    floor:         Optional[str]   = None
    address:       Optional[str]   = None
    district:      Optional[str]   = None
    social_status: str             = "market"
    description:   Optional[str]   = None
    image_url:     Optional[str]   = None
    published_at:  Optional[str]   = None
    extras:        dict            = field(default_factory=dict)

    def matches(self, f: ApartmentFilter) -> bool:
        if f.min_rooms  is not None and self.rooms is not None and self.rooms  < f.min_rooms:  return False
        if f.max_rooms  is not None and self.rooms is not None and self.rooms  > f.max_rooms:  return False
        if f.min_sqm    is not None and self.sqm   is not None and self.sqm    < f.min_sqm:    return False
        if f.max_sqm    is not None and self.sqm   is not None and self.sqm    > f.max_sqm:    return False
        if f.min_price  is not None and self.price is not None and self.price  < f.min_price:  return False
        if f.max_price  is not None and self.price is not None and self.price  > f.max_price:  return False
        if f.social_status != "any" and self.social_status != "unknown":
            if self.social_status != f.social_status:                          return False
        text = (self.title + " " + (self.description or "")).lower()
        if f.exclude_keywords and any(kw.lower() in text for kw in f.exclude_keywords): return False
        if f.include_keywords and not any(kw.lower() in text for kw in f.include_keywords): return False
        return True

    def to_telegram_message(self, lang: str = "en") -> str:
        """
        Render a Telegram HTML notification in the given UI language.
        German domain values (WBS, Sozialwohnung, etc.) are translated
        via _STATUS_LABELS — they never appear raw in the output.
        """
        lb     = _APARTMENT_LABELS.get(lang, _APARTMENT_LABELS["en"])
        status = _STATUS_LABELS.get(lang, _STATUS_LABELS["en"])

        lines  = [f"🏠 <b>{self.title}</b>", f"🌐 <i>{self.source}</i>", ""]

        if self.price is not None:
            lines.append(f"{lb['price']} {self.price:,.0f} {self.currency} {lb['price_unit']}")
        if self.rooms is not None:
            lines.append(f"{lb['rooms']} {self.rooms}")
        if self.sqm is not None:
            lines.append(f"{lb['area']} {self.sqm} {lb['area_unit']}")
        if self.floor:
            lines.append(f"{lb['floor']} {self.floor}")
        if self.address or self.district:
            loc = ", ".join(filter(None, [self.district, self.address]))
            lines.append(f"{lb['location']} {loc}")

        lines.append(f"{lb['status']} {status.get(self.social_status, self.social_status)}")

        if self.published_at:
            lines.append(f"{lb['published']} {self.published_at}")

        lines += ["", f'🔗 <a href="{self.url}">{lb["link"]}</a>']
        return "\n".join(lines)