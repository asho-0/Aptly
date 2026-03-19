from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.enums import SocialStatus


@dataclass
class ApartmentFilterBase(ABC):
    min_rooms: int | None = None
    max_rooms: int | None = None
    min_sqm: float | None = None
    max_sqm: float | None = None
    min_price: float | None = None
    max_price: float | None = None
    social_status: SocialStatus = SocialStatus.ANY

    @abstractmethod
    def summary(self, lang: str = "en") -> str: ...

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


@dataclass
class ApartmentBase(ABC):
    id: str
    source: str
    url: str
    title: str
    price: float | None = None  # Gesamtmiete (warm total)
    cold_rent: float | None = None  # Kaltmiete
    extra_costs: float | None = None  # Nebenkosten
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

    @abstractmethod
    def matches(self, apartment_filter: ApartmentFilterBase) -> bool: ...

    @abstractmethod
    def to_telegram_message(self) -> str: ...
