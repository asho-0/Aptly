# ============================================================
# services/scrape_run_service.py — Scrape run orchestration
# ============================================================

import logging
from typing import Optional

from database import db
from repositories.scrape import ScrapeRunRepository
from schemas.scrape import BeginRunRequest, FinishRunRequest

logger = logging.getLogger(__name__)


class ScrapeRunService:
    """Manages the lifecycle of a scraper run (start, finish/error)."""

    def __init__(self) -> None:
        self._repo = ScrapeRunRepository()

    async def begin_run(self, source_slug: str) -> int:
        req = BeginRunRequest(source_slug=source_slug)
        async with db.session_context():
            res = await self._repo.begin(req)
            return res.run_id

    async def finish_run(
        self, run_id: int, found: int, new: int, error: Optional[str] = None
    ) -> None:
        req = FinishRunRequest(run_id=run_id, found=found, new=new, error=error)
        async with db.session_context():
            await self._repo.finish(req)