# ============================================================
# schemas/filter.py — Pydantic I/O contracts for filter ops
# ============================================================

from typing import Optional
from pydantic import BaseModel

class LoadFilterRequest(BaseModel):
    chat_id: str

class FilterResponse(BaseModel):
    min_rooms:        Optional[int]
    max_rooms:        Optional[int]
    min_sqm:          Optional[float]
    max_sqm:          Optional[float]
    min_price:        Optional[float]
    max_price:        Optional[float]
    social_status:    str
    include_keywords: list[str]
    exclude_keywords: list[str]
    paused:           bool

class SaveFilterRequest(BaseModel):
    chat_id:          str
    min_rooms:        Optional[int]   = None
    max_rooms:        Optional[int]   = None
    min_sqm:          Optional[float] = None
    max_sqm:          Optional[float] = None
    min_price:        Optional[float] = None
    max_price:        Optional[float] = None
    social_status:    str             = "market"
    include_keywords: list[str]       = []
    exclude_keywords: list[str]       = []
    paused:           bool            = False

class SetPausedRequest(BaseModel):
    chat_id: str
    paused:  bool

class UpdateFilterFieldRequest(BaseModel):
    chat_id: str
    field:   str
    value:   str

class UpdateKeywordsRequest(BaseModel):
    chat_id: str
    add:     list[str] = []
    remove:  list[str] = []