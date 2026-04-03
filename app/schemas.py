from datetime import date, datetime

from pydantic import BaseModel


class TrialResponse(BaseModel):
    id: int
    registry_id: str
    registry_source: str
    brief_title: str | None = None
    official_title: str | None = None
    status: str | None = None
    phase: str | None = None
    study_type: str | None = None
    brief_summary: str | None = None
    conditions: list | None = None
    interventions: list | None = None
    primary_outcome: list | None = None
    eligibility_criteria: str | None = None
    locations: list | None = None
    sponsor: str | None = None
    enrollment_count: int | None = None
    start_date: date | None = None
    completion_date: date | None = None
    last_updated: datetime | None = None
    harvested_at: datetime

    model_config = {"from_attributes": True}


class TrialListResponse(BaseModel):
    data: list[TrialResponse]
    total: int
    limit: int
    offset: int
    cursor: datetime | None = None


class HarvestStatusResponse(BaseModel):
    is_running: bool
    pages_fetched: int
    total_records: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class StatsResponse(BaseModel):
    total_trials: int
    last_harvest: datetime | None = None
    status: str
