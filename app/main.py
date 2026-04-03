import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import engine
from app.models import Base
from app.api import trials, harvest

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


@app.get("/")
async def root():
    from app.services.harvester import harvest_manager
    status = "harvesting" if harvest_manager.status.is_running else "idle"
    return {"status": status, "service": "clinical-trials-middleware"}
