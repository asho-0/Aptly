import typing as t

from pydantic import BaseModel, field_validator

from app.core.enums import SocialStatus


class UpsertListingRequest(BaseModel):
    uid: str
    source_slug: str
    source_name: str
    external_id: str
    title: str
    url: str
    price: t.Optional[float] = None
    currency: str = "EUR"
    rooms: t.Optional[int] = None
    sqm: t.Optional[float] = None
    floor: t.Optional[str] = None
    address: t.Optional[str] = None
    district: t.Optional[str] = None
    social_status: SocialStatus
    description: t.Optional[str] = None
    image_url: t.Optional[str] = None
    published_at: t.Optional[str] = None

    @field_validator("price")
    @classmethod
    def price_must_be_positive(cls, v: t.Optional[float]) -> t.Optional[float]:
        if v is not None and v < 0:
            raise ValueError("Price must be non-negative")
        return v

    @field_validator("rooms")
    @classmethod
    def rooms_must_be_positive(cls, v: t.Optional[int]) -> t.Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("Room count must be positive")
        return v

    @field_validator("sqm")
    @classmethod
    def sqm_must_be_positive(cls, v: t.Optional[float]) -> t.Optional[float]:
        if v is not None and v <= 0:
            raise ValueError("Area must be positive")
        return v

    @field_validator("currency")
    @classmethod
    def currency_must_be_3_chars(cls, v: str) -> str:
        if len(v) != 3:
            raise ValueError("Currency must be a 3-letter ISO code")
        return v.upper()

    @field_validator("uid")
    @classmethod
    def uid_must_have_slug_prefix(cls, v: str) -> str:
        if ":" not in v:
            raise ValueError("UID must follow format '{slug}:{external_id}'")
        return v


class MarkNotifiedRequest(BaseModel):
    listing_db_id: int
    chat_id: str
    uid: str


class GetNotifiedUIDsRequest(BaseModel):
    pass


class ListingStatsRequest(BaseModel):
    source_slug: t.Optional[str] = None
    only_active: bool = True
    max_rows: int = 20

    @field_validator("max_rows")
    @classmethod
    def max_rows_in_range(cls, v: int) -> int:
        if not (1 <= v <= 200):
            raise ValueError("max_rows must be between 1 and 200")
        return v


class UpsertListingResponse(BaseModel):
    listing_db_id: int
    is_new: bool


class PriceStatsRow(BaseModel):
    source_slug: str
    rooms: t.Optional[int]
    total: int
    avg_price: float
    min_price: float
    max_price: float


class ListingCountResponse(BaseModel):
    total_all_time: int
    total_today: int
