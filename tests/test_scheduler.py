from __future__ import annotations

from apscheduler.triggers.interval import IntervalTrigger
from test_ingest import FakeClient

from voidbroker.config import Settings
from voidbroker.ingest import full_ingest
from voidbroker.scheduler import JOB_ID, build_scheduler, make_ingest_job
from voidbroker.storage import Storage


def test_build_scheduler_registers_single_interval_job():
    scheduler = build_scheduler(Settings(), interval_hours=6)
    jobs = scheduler.get_jobs()
    assert len(jobs) == 1
    job = jobs[0]
    assert job.id == JOB_ID
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval.total_seconds() == 6 * 3600


async def test_full_ingest_end_to_end(storage, sample_item_raw, sample_weapon_raw,
                                      sample_stat_rows, sample_orders_raw,
                                      sample_riven_attr_raw, sample_auction_raw):
    from voidbroker.models import (
        Item,
        Order,
        RivenAttribute,
        RivenAuction,
        RivenWeapon,
        StatRecord,
    )

    client = FakeClient(
        items=[Item.from_api(sample_item_raw, "en")],
        weapons=[RivenWeapon.from_api(sample_weapon_raw, "en")],
        stats=[StatRecord.model_validate(r) for r in sample_stat_rows],
        orders=[Order.model_validate(o) for o in sample_orders_raw],
        attrs=[RivenAttribute.from_api(sample_riven_attr_raw, "en")],
        auctions=[RivenAuction.from_api(sample_auction_raw)],
    )
    report = await full_ingest(client, storage, orders=True, rivens=True)

    assert report.items == 1
    assert report.riven_weapons == 1
    assert report.price_rows == 2
    assert report.order_snapshots == 1
    assert report.riven_attributes == 1
    assert report.riven_auctions == 1
    assert storage.count("riven_auctions") == 1


async def test_make_ingest_job_swallows_errors(monkeypatch):
    """A failing tick must not raise out of the job (it would kill the scheduler)."""
    settings = Settings(db_path=":memory:")

    async def boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr("voidbroker.scheduler.full_ingest", boom)
    job = make_ingest_job(settings)
    await job()  # should not raise


def test_storage_smoke_for_scheduler_path():
    # Sanity: the job builds a Storage at the configured path without error.
    s = Storage(":memory:")
    assert s.count("items") == 0
    s.close()
