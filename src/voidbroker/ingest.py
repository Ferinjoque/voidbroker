"""Ingestion orchestration, the jobs that build and refresh the local archive.

Network calls are paced globally by the client's rate limiter, so fanning out with
``asyncio`` here is safe and polite; a bounded semaphore keeps in-flight requests and
memory modest even across the full ~3800-item catalog.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass

from .client import WarframeMarketClient
from .metrics import aggregate_orders
from .storage import Storage
from .worldstate import fetch_resurgence, fetch_void_trader

ProgressCb = Callable[[int, int], None] | None

log = logging.getLogger("voidbroker.ingest")


@dataclass
class CatalogResult:
    items: int
    riven_weapons: int


async def sync_catalog(client: WarframeMarketClient, storage: Storage) -> CatalogResult:
    """Refresh the item + riven-weapon catalogs (also snapshots disposition)."""
    items = await client.get_items()
    weapons = await client.get_riven_weapons()
    storage.upsert_items(items)
    storage.upsert_riven_weapons(weapons)
    return CatalogResult(items=len(items), riven_weapons=len(weapons))


async def _bounded_gather(coros: list, concurrency: int, on_progress: ProgressCb) -> list:
    sem = asyncio.Semaphore(concurrency)
    total = len(coros)
    done = 0
    results: list = []

    async def _run(coro):
        nonlocal done
        async with sem:
            try:
                result = await coro
            except Exception:  # one bad slug must not abort the whole sweep
                result = None
            done += 1
            if on_progress:
                on_progress(done, total)
            return result

    for chunk_result in await asyncio.gather(*(_run(c) for c in coros)):
        results.append(chunk_result)
    return results


async def ingest_statistics(
    client: WarframeMarketClient,
    storage: Storage,
    slugs: list[str],
    window: str = "90days",
    concurrency: int = 8,
    on_progress: ProgressCb = None,
) -> int:
    """Pull price history for each slug and upsert candlesticks. Returns rows written."""

    async def _one(slug: str) -> int:
        try:
            records = await client.get_statistics(slug, window=window)
            n = storage.upsert_price_history(slug, records)
            storage.record_fetch("prices", slug, ok=True)
            return n
        except Exception as exc:  # record the failure so the ref isn't starved forever
            storage.record_fetch("prices", slug, ok=False, error=str(exc))
            log.warning("prices fetch failed for %s: %s", slug, exc)
            return 0

    counts = await _bounded_gather([_one(s) for s in slugs], concurrency, on_progress)
    return sum(c for c in counts if c)


async def snapshot_orders(
    client: WarframeMarketClient,
    storage: Storage,
    slugs: list[str],
    concurrency: int = 8,
    on_progress: ProgressCb = None,
) -> int:
    """Capture a live order-book aggregate for each slug. Returns snapshots written."""

    async def _one(slug: str) -> int:
        try:
            orders = await client.get_orders(slug)
            storage.record_order_snapshot(slug, aggregate_orders(orders))
            storage.record_fetch("orders", slug, ok=True)
            return 1
        except Exception as exc:
            storage.record_fetch("orders", slug, ok=False, error=str(exc))
            log.warning("orders fetch failed for %s: %s", slug, exc)
            return 0

    counts = await _bounded_gather([_one(s) for s in slugs], concurrency, on_progress)
    return sum(c for c in counts if c)


async def ingest_item_details(
    client: WarframeMarketClient,
    storage: Storage,
    slugs: list[str],
    concurrency: int = 8,
    on_progress: ProgressCb = None,
) -> int:
    """Pull per-item detail (ducats, set composition) and upsert. Returns rows written."""

    async def _one(slug: str) -> int:
        try:
            detail = await client.get_item_detail(slug)
            storage.upsert_item_details([detail])
            storage.record_fetch("details", slug, ok=True)
            return 1
        except Exception as exc:
            storage.record_fetch("details", slug, ok=False, error=str(exc))
            log.warning("item detail fetch failed for %s: %s", slug, exc)
            return 0

    counts = await _bounded_gather([_one(s) for s in slugs], concurrency, on_progress)
    return sum(c for c in counts if c)


async def sync_riven_attributes(client: WarframeMarketClient, storage: Storage) -> int:
    """Refresh the riven attribute catalog (the appraisal vocabulary)."""
    attrs = await client.get_riven_attributes()
    storage.upsert_riven_attributes(attrs)
    return len(attrs)


async def ingest_riven_auctions(
    client: WarframeMarketClient,
    storage: Storage,
    weapon_slugs: list[str],
    concurrency: int = 8,
    on_progress: ProgressCb = None,
) -> int:
    """Snapshot live riven auctions per weapon. Returns auction rows written."""

    async def _one(slug: str) -> int:
        try:
            auctions = await client.search_riven_auctions(slug)
            n = storage.record_riven_auctions(slug, auctions)
            storage.record_fetch("auctions", slug, ok=True)
            return n
        except Exception as exc:
            storage.record_fetch("auctions", slug, ok=False, error=str(exc))
            log.warning("auctions fetch failed for %s: %s", slug, exc)
            return 0

    counts = await _bounded_gather([_one(s) for s in weapon_slugs], concurrency, on_progress)
    return sum(c for c in counts if c)


async def sync_void_trader(storage: Storage, platform: str = "pc") -> bool:
    """Snapshot Baro Ki'Teer's current state (a scheduled price catalyst)."""
    state = await fetch_void_trader(platform=platform)
    storage.record_void_trader(state)
    return True


async def sync_resurgence(storage: Storage, platform: str = "pc") -> bool:
    """Snapshot Varzia's Prime Resurgence rotation (the vault-cycle price catalyst)."""
    state = await fetch_resurgence(platform=platform)
    storage.record_resurgence(state)
    return True


@dataclass
class IngestReport:
    items: int = 0
    riven_weapons: int = 0
    price_rows: int = 0
    detail_rows: int = 0
    order_snapshots: int = 0
    riven_attributes: int = 0
    riven_auctions: int = 0
    void_trader: bool = False
    resurgence: bool = False


async def seed_ingest(
    client: WarframeMarketClient,
    storage: Storage,
    *,
    item_count: int = 60,
    weapon_count: int = 12,
    worldstate: bool = True,
    on_progress: ProgressCb = None,
) -> IngestReport:
    """Build a small but representative archive so a freshly cloned repo shows live signals
    immediately instead of empty views.

    The slug list is derived FROM the just-synced catalog (Prime gear: it carries the most
    volume, ducats, and set composition), so the slugs are always valid and every signal
    lights up: prices feed Markets/Opportunities, order books feed the liquidity score,
    details feed Arbitrage/Ducats, riven auctions feed Riven Deals, and worldstate feeds
    Baro/Resurgence. This is a one-shot demo populate, not the compounding scheduled sweep.
    """
    report = IngestReport()
    catalog = await sync_catalog(client, storage)
    report.items = catalog.items
    report.riven_weapons = catalog.riven_weapons

    item_slugs = [
        r["slug"]
        for r in storage._rows(
            "SELECT slug FROM items WHERE lower(slug) LIKE '%prime%' ORDER BY slug LIMIT ?",
            [item_count],
        )
    ]
    report.price_rows = await ingest_statistics(
        client, storage, item_slugs, on_progress=on_progress
    )
    report.order_snapshots = await snapshot_orders(client, storage, item_slugs)
    report.detail_rows = await ingest_item_details(client, storage, item_slugs)

    report.riven_attributes = await sync_riven_attributes(client, storage)
    weapon_slugs = [
        r["slug"]
        for r in storage._rows(
            "SELECT slug FROM riven_weapons ORDER BY slug LIMIT ?", [weapon_count]
        )
    ]
    report.riven_auctions = await ingest_riven_auctions(client, storage, weapon_slugs)

    if worldstate:
        report.void_trader = await sync_void_trader(storage, platform=client.settings.platform)
        report.resurgence = await sync_resurgence(storage, platform=client.settings.platform)

    return report


async def full_ingest(
    client: WarframeMarketClient,
    storage: Storage,
    *,
    window: str = "90days",
    orders: bool = False,
    rivens: bool = False,
    worldstate: bool = False,
    details: bool = False,
    item_limit: int | None = None,
    batch: int | None = None,
    auction_batch: int | None = None,
) -> IngestReport:
    """Headless end-to-end ingest used by the scheduler (and any non-interactive caller).

    Mirrors the CLI's steps without the rich progress UI, logging a line per stage.

    When ``batch`` is set, each per-item source processes only the *stalest* ``batch`` refs
    (never-fetched first), so a recurring run sweeps the whole catalog over time instead of
    re-fetching everything every tick. ``item_limit`` (first-N alphabetical) is the older
    testing knob and only applies when ``batch`` is None. The catalog + disposition sync
    always covers every weapon (it's a single cheap call), so disposition history never
    goes stale regardless of batch size.

    Riven auction snapshots are far heavier than prices/orders (~seconds per weapon, with
    hundreds of rows each), so ``auction_batch`` lets them sweep at a smaller, separate size
    to keep a scheduled run quick. Defaults to ``batch`` when unset.
    """
    report = IngestReport()

    catalog = await sync_catalog(client, storage)
    report.items = catalog.items
    report.riven_weapons = catalog.riven_weapons
    log.info("catalog: %d items, %d riven weapons", catalog.items, catalog.riven_weapons)

    if batch:
        item_slugs = storage.stalest_refs("prices", batch)
    else:
        item_slugs = [r["slug"] for r in storage._rows("SELECT slug FROM items ORDER BY slug")]
        if item_limit:
            item_slugs = item_slugs[:item_limit]

    report.price_rows = await ingest_statistics(client, storage, item_slugs, window=window)
    log.info("price history: %d rows", report.price_rows)

    if orders:
        order_slugs = storage.stalest_refs("orders", batch) if batch else item_slugs
        report.order_snapshots = await snapshot_orders(client, storage, order_slugs)
        log.info("order snapshots: %d", report.order_snapshots)

    if details:
        detail_slugs = storage.stalest_refs("details", batch) if batch else item_slugs
        report.detail_rows = await ingest_item_details(client, storage, detail_slugs)
        log.info("item details: %d rows", report.detail_rows)

    if rivens:
        report.riven_attributes = await sync_riven_attributes(client, storage)
        a_batch = auction_batch or batch
        if a_batch:
            weapon_slugs = storage.stalest_refs("auctions", a_batch)
        else:
            weapon_slugs = [
                r["slug"] for r in storage._rows("SELECT slug FROM riven_weapons ORDER BY slug")
            ]
            if item_limit:
                weapon_slugs = weapon_slugs[:item_limit]
        report.riven_auctions = await ingest_riven_auctions(client, storage, weapon_slugs)
        log.info(
            "rivens: %d attributes, %d auction rows",
            report.riven_attributes, report.riven_auctions,
        )

    if worldstate:
        report.void_trader = await sync_void_trader(storage, platform=client.settings.platform)
        report.resurgence = await sync_resurgence(storage, platform=client.settings.platform)
        log.info("worldstate: void trader + resurgence snapshots recorded")

    return report
