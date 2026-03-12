# ============================================================
# repositories/scrape.py — ScrapeRun DB access layer
# ============================================================

from datetime import datetime, timezone

from sqlalchemy import update

from db_models import ScrapeRun
from repositories.base import BaseRepository
from schemas.scrape import BeginRunRequest, BeginRunResponse, FinishRunRequest


class ScrapeRunRepository(BaseRepository):

    async def begin(self, req: BeginRunRequest) -> BeginRunResponse:
        run = ScrapeRun(source_slug=req.source_slug)
        self.session.add(run)
        await self.session.flush()  # populate run.id without committing
        return BeginRunResponse(run_id=run.id)

    async def finish(self, req: FinishRunRequest) -> None:
        await self.session.execute(
            update(ScrapeRun)
            .where(ScrapeRun.id == req.run_id)
            .values(
                finished_at    = datetime.now(timezone.utc),
                listings_found = req.found,
                new_listings   = req.new,
                error_msg      = req.error,
                success        = (req.error is None),
            )
        )