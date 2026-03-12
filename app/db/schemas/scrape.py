# ============================================================
# schemas/scrape.py — Pydantic I/O contracts for scrape runs
# ============================================================

from typing import Optional
from pydantic import BaseModel

class BeginRunRequest(BaseModel):
    source_slug: str

class BeginRunResponse(BaseModel):
    run_id: int

class FinishRunRequest(BaseModel):
    run_id: int
    found:  int
    new:    int
    error:  Optional[str] = None