from sqlalchemy import BigInteger, String, Boolean, DateTime, Numeric, Text, ForeignKey, Index, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional
import datetime

from app.db.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(128))
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    language: Mapped[str] = mapped_column(String(10), server_default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true", index=True)
    
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    filter: Mapped["Filter"] = relationship(
        "Filter", back_populates="user", cascade="all, delete-orphan", uselist=False
    )

    notifications: Mapped[list["NotifiedListing"]] = relationship("NotifiedListing", back_populates="user")


class Filter(Base):
    __tablename__ = "filters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.chat_id", ondelete="CASCADE"), unique=True
    )
    paused: Mapped[bool] = mapped_column(Boolean, server_default="false", nullable=False, index=True)
    
    min_rooms: Mapped[Optional[int]] = mapped_column(SmallInteger)
    max_rooms: Mapped[Optional[int]] = mapped_column(SmallInteger)
    min_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    max_price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2))
    min_sqm: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    max_sqm: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    
    social_status: Mapped[str] = mapped_column(String(32), server_default="any")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="filter")


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    uid: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    source_slug: Mapped[str] = mapped_column(String(50), index=True)
    external_id: Mapped[str] = mapped_column(String(100), index=True) 
    
    source_name: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    price: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), index=True)
    currency: Mapped[str] = mapped_column(String(10), server_default="EUR")
    rooms: Mapped[Optional[int]] = mapped_column(SmallInteger, index=True)
    sqm: Mapped[Optional[float]] = mapped_column(Numeric(8, 2))
    floor: Mapped[Optional[int]] = mapped_column(SmallInteger)
    address: Mapped[Optional[str]] = mapped_column(Text)
    district: Mapped[Optional[str]] = mapped_column(String(128), index=True)
    social_status: Mapped[str] = mapped_column(String(32), server_default="any", index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    image_url: Mapped[Optional[str]] = mapped_column(Text)

    active: Mapped[bool] = mapped_column(Boolean, server_default="true", index=True)
    
    notified: Mapped[bool] = mapped_column(Boolean, server_default="false", index=True)
    notified_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True))
    
    published_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), index=True)
    first_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    notified_records: Mapped[list["NotifiedListing"]] = relationship(
        "NotifiedListing", 
        back_populates="listing", 
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("uq_listing_source_ext", "source_slug", "external_id", unique=True),
        Index("ix_listing_stats", "source_slug", "rooms", "price", "active"),
    )



class NotifiedListing(Base):
    __tablename__ = "notified_listings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    
    uid: Mapped[str] = mapped_column(String(255), ForeignKey("listings.uid", ondelete="CASCADE"), index=True)
    chat_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.chat_id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="notifications")
    listing: Mapped["Listing"] = relationship("Listing", back_populates="notified_records")

    __table_args__ = (
        Index("uq_notified_user_apt", "uid", "chat_id", unique=True),
    )