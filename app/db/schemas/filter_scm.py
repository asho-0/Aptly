import typing as t

from pydantic import BaseModel

from app.core.enums import SocialStatus


class LoadFilterRequest(BaseModel):
    chat_id: str


class FilterResponse(BaseModel):
    min_rooms: t.Optional[int]
    max_rooms: t.Optional[int]
    min_sqm: t.Optional[float]
    max_sqm: t.Optional[float]
    min_price: t.Optional[float]
    max_price: t.Optional[float]
    social_status: str
    paused: bool


class SaveFilterRequest(BaseModel):
    chat_id: str
    min_rooms: t.Optional[int] = None
    max_rooms: t.Optional[int] = None
    min_sqm: t.Optional[float] = None
    max_sqm: t.Optional[float] = None
    min_price: t.Optional[float] = None
    max_price: t.Optional[float] = None
    social_status: SocialStatus
    paused: bool = False
    lang: str = "en"


class SetPausedRequest(BaseModel):
    chat_id: str
    paused: bool
    lang: str = "en"


class UpdateFilterFieldRequest(BaseModel):
    chat_id: str
    field: str
