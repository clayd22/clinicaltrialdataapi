import asyncio
import logging
from datetime import date, datetime, timedelta

from app.config import settings
from app.services.harvester import harvest_manager

logger = logging.getLogger(__name__)


class HarvestScheduler:
    """Internal scheduler that keeps the database fresh.

    - Hourly: fetches trials updated in the last 2 hours (configurable).
      Catches new/modified trials with minimal overhead.
    - Daily: wider sweep of the last 48 hours (configurable).
      Safety net to catch anything the hourly runs might have missed
      due to CT.gov posting delays or transient failures.

    Upserts make overlap harmless — re-fetching a trial just updates the row.
    """

    def __init__(self):
        self._hourly_task: asyncio.Task | None = None
        self._daily_task: asyncio.Task | None = None
        self._running = False

    async def start(self):
        self._running = True
        self._hourly_task = asyncio.create_task(self._hourly_loop())
        self._daily_task = asyncio.create_task(self._daily_loop())
        logger.info(
            "Harvest scheduler started — hourly every %ds, daily every %ds",
            settings.hourly_interval,
            settings.daily_interval,
        )

    async def stop(self):
        self._running = False
        for task in [self._hourly_task, self._daily_task]:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        logger.info("Harvest scheduler stopped")

    async def _hourly_loop(self):
        # Small initial delay so the app finishes starting up
        await asyncio.sleep(10)
        while self._running:
            try:
                await self._run_incremental(settings.hourly_lookback_hours)
            except Exception:
                logger.exception("Hourly harvest failed")
            await asyncio.sleep(settings.hourly_interval)

    async def _daily_loop(self):
        # Offset from hourly so they don't collide
        await asyncio.sleep(60)
        while self._running:
            try:
                await self._run_incremental(settings.daily_lookback_hours)
            except Exception:
                logger.exception("Daily sweep failed")
            await asyncio.sleep(settings.daily_interval)

    async def _run_incremental(self, lookback_hours: int):
        if harvest_manager.status.is_running:
            logger.info("Harvest already running, skipping scheduled run")
            return
        since = date.today() - timedelta(hours=lookback_hours)
        logger.info(
            "Scheduled harvest: fetching trials updated since %s (%dh lookback)",
            since, lookback_hours,
        )
        await harvest_manager.start_incremental_harvest(since)
        if harvest_manager.status.error:
            logger.error("Scheduled harvest completed with error: %s", harvest_manager.status.error)
        else:
            logger.info(
                "Scheduled harvest complete: %d records in %d pages",
                harvest_manager.status.total_records,
                harvest_manager.status.pages_fetched,
            )


scheduler = HarvestScheduler()
