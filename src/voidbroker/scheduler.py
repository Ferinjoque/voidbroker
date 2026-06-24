"""Recurring ingestion, the cadence that makes the archive a moat.

A single interval job runs ``full_ingest`` on a schedule. The longer it runs, the more
price/disposition/auction history voidbroker holds that nobody can retroactively obtain.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from .client import WarframeMarketClient
from .config import Settings, get_settings
from .ingest import full_ingest
from .storage import Storage

log = logging.getLogger("voidbroker.scheduler")

JOB_ID = "full_ingest"


def make_ingest_job(
    settings: Settings,
    *,
    orders: bool = True,
    rivens: bool = True,
    worldstate: bool = True,
    item_limit: int | None = None,
    batch: int | None = None,
    auction_batch: int | None = None,
) -> Callable[[], Awaitable[None]]:
    """Build the coroutine the scheduler fires each tick: one self-contained ingest run."""

    async def job() -> None:
        storage = Storage(settings.db_path)
        try:
            async with WarframeMarketClient(settings) as client:
                report = await full_ingest(
                    client, storage, orders=orders, rivens=rivens,
                    worldstate=worldstate, item_limit=item_limit, batch=batch,
                    auction_batch=auction_batch,
                )
            log.info("ingest complete: %s", report)
        except Exception:  # a failed tick must not kill the scheduler
            log.exception("scheduled ingest failed")
        finally:
            storage.close()

    return job


def build_scheduler(
    settings: Settings | None = None,
    *,
    interval_hours: float = 12.0,
    orders: bool = True,
    rivens: bool = True,
    worldstate: bool = True,
    item_limit: int | None = None,
    batch: int | None = None,
    auction_batch: int | None = None,
) -> AsyncIOScheduler:
    """Create (but do not start) a scheduler with the single recurring ingest job."""
    settings = settings or get_settings()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        make_ingest_job(
            settings, orders=orders, rivens=rivens,
            worldstate=worldstate, item_limit=item_limit, batch=batch,
            auction_batch=auction_batch,
        ),
        trigger=IntervalTrigger(hours=interval_hours),
        id=JOB_ID,
        max_instances=1,        # never overlap runs
        coalesce=True,          # if we fell behind, run once not N times
        replace_existing=True,
    )
    return scheduler
