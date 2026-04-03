import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime

import httpx
from sqlalchemy import text
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.config import settings
from app.database import async_session
from app.models import Trial
from app.services.transformer import transform_ctgov_study

logger = logging.getLogger(__name__)


@dataclass
class HarvestStatus:
    is_running: bool = False
    pages_fetched: int = 0
    total_records: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class HarvestManager:
    def __init__(self):
        self.status = HarvestStatus()

    async def start_full_harvest(self):
        if self.status.is_running:
            return
        self._reset_status()
        try:
            await self._harvest(query_params={})
        except Exception as e:
            logger.exception("Full harvest failed")
            self.status.error = str(e)
        finally:
            self.status.is_running = False
            self.status.completed_at = datetime.utcnow()

    async def start_incremental_harvest(self, since: date | None = None):
        if self.status.is_running:
            return
        self._reset_status()
        if since is None:
            since = date.today()
        date_range = f"AREA[LastUpdatePostDate]RANGE[{since.strftime('%m/%d/%Y')},{date.today().strftime('%m/%d/%Y')}]"
        try:
            await self._harvest(query_params={"filter.advanced": date_range})
        except Exception as e:
            logger.exception("Incremental harvest failed")
            self.status.error = str(e)
        finally:
            self.status.is_running = False
            self.status.completed_at = datetime.utcnow()

    def _reset_status(self):
        self.status = HarvestStatus(
            is_running=True,
            started_at=datetime.utcnow(),
        )

    async def _harvest(self, query_params: dict):
        params = {
            "pageSize": settings.ctgov_page_size,
            **query_params,
        }
        page_token = None

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                if page_token:
                    params["pageToken"] = page_token

                resp = await client.get(
                    f"{settings.ctgov_base_url}/studies",
                    params=params,
                )
                resp.raise_for_status()
                data = resp.json()

                studies = data.get("studies", [])
                if studies:
                    await self._store_batch(studies)
                    self.status.total_records += len(studies)

                self.status.pages_fetched += 1
                logger.info(
                    f"Page {self.status.pages_fetched}: {len(studies)} studies "
                    f"(total: {self.status.total_records})"
                )

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

                await asyncio.sleep(settings.harvest_delay)

    async def _store_batch(self, studies: list[dict]):
        rows = []
        for study in studies:
            transformed = transform_ctgov_study(study)
            if not transformed["registry_id"]:
                continue
            transformed["harvested_at"] = datetime.utcnow()
            rows.append(transformed)

        if not rows:
            return

        async with async_session() as session:
            stmt = sqlite_insert(Trial).values(rows)
            stmt = stmt.on_conflict_do_update(
                index_elements=["registry_source", "registry_id"],
                set_={
                    "brief_title": stmt.excluded.brief_title,
                    "official_title": stmt.excluded.official_title,
                    "status": stmt.excluded.status,
                    "phase": stmt.excluded.phase,
                    "study_type": stmt.excluded.study_type,
                    "brief_summary": stmt.excluded.brief_summary,
                    "conditions": stmt.excluded.conditions,
                    "interventions": stmt.excluded.interventions,
                    "primary_outcome": stmt.excluded.primary_outcome,
                    "eligibility_criteria": stmt.excluded.eligibility_criteria,
                    "locations": stmt.excluded.locations,
                    "sponsor": stmt.excluded.sponsor,
                    "enrollment_count": stmt.excluded.enrollment_count,
                    "start_date": stmt.excluded.start_date,
                    "completion_date": stmt.excluded.completion_date,
                    "last_updated": stmt.excluded.last_updated,
                    "harvested_at": stmt.excluded.harvested_at,
                    "raw_json": stmt.excluded.raw_json,
                },
            )
            await session.execute(stmt)
            await session.commit()


harvest_manager = HarvestManager()
