import asyncio
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query

from app.schemas import HarvestStatusResponse
from app.services.harvester import harvest_manager

router = APIRouter(prefix="/harvest", tags=["harvest"])


@router.post("/trigger", status_code=202)
async def trigger_harvest(
    full: bool = Query(False, description="Full harvest (all trials) vs incremental"),
    since: date | None = Query(None, description="For incremental: start date (defaults to yesterday)"),
):
    if harvest_manager.status.is_running:
        raise HTTPException(status_code=409, detail="Harvest already in progress")

    if full:
        asyncio.create_task(harvest_manager.start_full_harvest())
        return {"message": "Full harvest started", "status_url": "/harvest/status"}
    else:
        if since is None:
            since = date.today() - timedelta(days=2)
        asyncio.create_task(harvest_manager.start_incremental_harvest(since))
        return {
            "message": f"Incremental harvest started (since {since})",
            "status_url": "/harvest/status",
        }


@router.get("/status", response_model=HarvestStatusResponse)
async def harvest_status():
    s = harvest_manager.status
    return HarvestStatusResponse(
        is_running=s.is_running,
        pages_fetched=s.pages_fetched,
        total_records=s.total_records,
        started_at=s.started_at,
        completed_at=s.completed_at,
        error=s.error,
    )
