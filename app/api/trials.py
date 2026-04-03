import csv
import io
import json
from datetime import date

from enum import Enum

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, get_session
from app.models import Trial
from app.schemas import TrialListResponse, TrialResponse

router = APIRouter(prefix="/trials", tags=["trials"])


@router.get("", response_model=TrialListResponse)
async def list_trials(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    status: str | None = None,
    registry_source: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    query = select(Trial)
    count_query = select(func.count(Trial.id))

    if status:
        query = query.where(Trial.status == status)
        count_query = count_query.where(Trial.status == status)
    if registry_source:
        query = query.where(Trial.registry_source == registry_source)
        count_query = count_query.where(Trial.registry_source == registry_source)

    total = (await session.execute(count_query)).scalar()
    results = (
        await session.execute(query.order_by(Trial.id).limit(limit).offset(offset))
    ).scalars().all()

    return TrialListResponse(
        data=[TrialResponse.model_validate(r) for r in results],
        total=total,
        limit=limit,
        offset=offset,
    )


class BulkFormat(str, Enum):
    csv = "csv"
    ndjson = "ndjson"


@router.get("/bulk")
async def bulk_export(
    format: BulkFormat = Query(BulkFormat.csv, description="Export format: csv or ndjson (ndjson recommended for nested fields)"),
):
    """Streaming bulk export of all trials.

    - **csv**: Comma-separated values (default). Simple but nested fields are flattened to strings.
    - **ndjson**: Newline-delimited JSON. Each line is a valid JSON object with proper arrays/objects.

    **Warning**: This streams the full dataset (~500K+ records). Use curl or a script, not a browser.
    """
    use_ndjson = format == BulkFormat.ndjson

    columns = [
        "registry_id", "registry_source", "brief_title", "official_title", "status",
        "phase", "study_type", "brief_summary", "conditions", "interventions",
        "primary_outcome", "eligibility_criteria", "locations",
        "sponsor", "enrollment_count", "start_date", "completion_date", "last_updated",
    ]

    async def _fetch_batches():
        """Keyset pagination — O(1) per batch instead of O(n) with OFFSET."""
        batch_size = 5000
        last_id = 0
        while True:
            async with async_session() as session:
                result = await session.execute(
                    select(Trial)
                    .where(Trial.id > last_id)
                    .order_by(Trial.id)
                    .limit(batch_size)
                )
                rows = result.scalars().all()
            if not rows:
                break
            yield rows
            last_id = rows[-1].id

    async def generate_ndjson():
        async for batch in _fetch_batches():
            for trial in batch:
                yield json.dumps(
                    {col: _serialize(getattr(trial, col)) for col in columns},
                    ensure_ascii=False,
                ) + "\n"

    async def generate_csv():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(columns)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)

        async for batch in _fetch_batches():
            for trial in batch:
                writer.writerow([getattr(trial, col) for col in columns])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    if use_ndjson:
        return StreamingResponse(
            generate_ndjson(),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": "attachment; filename=clinical_trials.ndjson"},
        )
    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=clinical_trials.csv"},
    )


def _serialize(value):
    """Serialize dates/datetimes to ISO strings for JSON output."""
    if isinstance(value, date):
        return value.isoformat()
    return value


@router.get("/updates", response_model=TrialListResponse)
async def get_updates(
    since: date = Query(..., description="Return trials updated on or after this date. Use the cursor from a previous response to resume."),
    limit: int = Query(1000, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """Incremental updates endpoint for daily harvesting.

    Returns trials updated since the given date, plus a **cursor** value.
    Pass the cursor as the `since` param on your next call to pick up where you left off.
    """
    query = select(Trial).where(Trial.last_updated >= since)
    count_query = select(func.count(Trial.id)).where(Trial.last_updated >= since)

    total = (await session.execute(count_query)).scalar()
    results = (
        await session.execute(
            query.order_by(Trial.last_updated.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()

    # cursor = max last_updated in this result set — use as `since` next time
    cursor = None
    if results:
        cursor = max(r.last_updated for r in results if r.last_updated)

    return TrialListResponse(
        data=[TrialResponse.model_validate(r) for r in results],
        total=total,
        limit=limit,
        offset=offset,
        cursor=cursor,
    )


@router.get("/{registry_id}", response_model=TrialResponse)
async def get_trial(
    registry_id: str,
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Trial).where(Trial.registry_id == registry_id)
    )
    trial = result.scalar_one_or_none()
    if not trial:
        raise HTTPException(status_code=404, detail="Trial not found")
    return TrialResponse.model_validate(trial)
