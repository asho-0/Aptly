import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models.base import Base


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    uid: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_slug: Mapped[str] = mapped_column(String(64), nullable=False)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="EUR")
    rooms: Mapped[Optional[int]] = mapped_column(SmallInteger)
    sqm: Mapped[Optional[float]] = mapped_column(Numeric(7, 2))
    floor: Mapped[Optional[str]] = mapped_column(String(32))
    address: Mapped[Optional[str]] = mapped_column(Text)
    district: Mapped[Optional[str]] = mapped_column(String(128))
    social_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="market"
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(Text)
    published_at: Mapped[Optional[str]] = mapped_column(String(64))

    first_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    last_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )
    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notified_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("uq_listing", "source_slug", "external_id", unique=True),
        Index("idx_listings_price", "price"),
        Index("idx_listings_rooms", "rooms"),
        Index("idx_listings_sqm", "sqm"),
        Index("idx_listings_social_status", "social_status"),
        Index("idx_listings_notified", "notified"),
        Index("idx_listings_first_seen", "first_seen_at"),
    )

    def __repr__(self) -> str:
        return f""


class Filter(Base):
    __tablename__ = "filters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    chat_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    min_rooms: Mapped[Optional[int]] = mapped_column(SmallInteger)
    max_rooms: Mapped[Optional[int]] = mapped_column(SmallInteger)
    min_sqm: Mapped[Optional[float]] = mapped_column(Numeric(7, 2))
    max_sqm: Mapped[Optional[float]] = mapped_column(Numeric(7, 2))
    min_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    max_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    social_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="any"
    )
    include_keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    exclude_keywords: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )
    paused: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )

    def __repr__(self) -> str:
        return f""
