import logging
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from sqlalchemy import func, select

from app.database import async_session, engine
from app.models import Base, Trial
from app.api import trials, harvest
from app.schemas import StatsResponse

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.scheduler import scheduler

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await scheduler.start()
    yield
    await scheduler.stop()
    await engine.dispose()


app = FastAPI(
    title="Clinical Trials Middleware",
    description=(
        "Abstraction layer for clinical trial registries. "
        "Harvests trials from ClinicalTrials.gov and exposes a unified API "
        "for bulk export and incremental updates."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(trials.router)
app.include_router(harvest.router)


@app.get("/", response_model=StatsResponse)
async def root():
    async with async_session() as session:
        total = (await session.execute(select(func.count(Trial.id)))).scalar()
        last = (
            await session.execute(
                select(func.max(Trial.harvested_at))
            )
        ).scalar()

    from app.services.harvester import harvest_manager
    status = "harvesting" if harvest_manager.status.is_running else "idle"

    return StatsResponse(
        total_trials=total,
        last_harvest=last,
        status=status,
    )
