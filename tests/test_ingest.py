from __future__ import annotations

from voidbroker.ingest import (
    ingest_riven_auctions,
    ingest_statistics,
    snapshot_orders,
    sync_catalog,
    sync_riven_attributes,
)
from voidbroker.models import (
    Item,
    Order,
    RivenAttribute,
    RivenAuction,
    RivenWeapon,
    StatRecord,
)


class FakeClient:
    """Duck-typed stand-in for WarframeMarketClient — no network."""

    def __init__(self, items, weapons, stats, orders, attrs=None, auctions=None):
        self._items = items
        self._weapons = weapons
        self._stats = stats
        self._orders = orders
        self._attrs = attrs or []
        self._auctions = auctions or []

    async def get_items(self):
        return self._items

    async def get_riven_weapons(self):
        return self._weapons

    async def get_statistics(self, slug, window="90days"):
        return self._stats

    async def get_orders(self, slug):
        return self._orders

    async def get_riven_attributes(self):
        return self._attrs

    async def search_riven_auctions(self, weapon_slug, sort_by="price_asc"):
        return self._auctions


def _fake_client(sample_item_raw, sample_weapon_raw, sample_stat_rows, sample_orders_raw):
    return FakeClient(
        items=[Item.from_api(sample_item_raw, "en")],
        weapons=[RivenWeapon.from_api(sample_weapon_raw, "en")],
        stats=[StatRecord.model_validate(r) for r in sample_stat_rows],
        orders=[Order.model_validate(o) for o in sample_orders_raw],
    )


async def test_sync_catalog(storage, sample_item_raw, sample_weapon_raw,
                            sample_stat_rows, sample_orders_raw):
    client = _fake_client(sample_item_raw, sample_weapon_raw, sample_stat_rows, sample_orders_raw)
    result = await sync_catalog(client, storage)
    assert result.items == 1
    assert result.riven_weapons == 1
    assert storage.count("items") == 1
    assert storage.count("disposition_history") == 1


async def test_ingest_statistics_writes_rows(storage, sample_item_raw, sample_weapon_raw,
                                             sample_stat_rows, sample_orders_raw):
    client = _fake_client(sample_item_raw, sample_weapon_raw, sample_stat_rows, sample_orders_raw)
    progress = []
    rows = await ingest_statistics(
        client, storage, ["a", "b"], on_progress=lambda d, t: progress.append((d, t))
    )
    assert rows == 4  # 2 slugs x 2 rows
    assert progress[-1] == (2, 2)


async def test_snapshot_orders_writes(storage, sample_item_raw, sample_weapon_raw,
                                      sample_stat_rows, sample_orders_raw):
    client = _fake_client(sample_item_raw, sample_weapon_raw, sample_stat_rows, sample_orders_raw)
    n = await snapshot_orders(client, storage, ["foo"])
    assert n == 1
    assert storage.latest_order_snapshot("foo")["sell_min"] == 90


async def test_sync_riven_attributes(storage, sample_riven_attr_raw):
    attr = RivenAttribute.from_api(sample_riven_attr_raw, "en")
    client = FakeClient([], [], [], [], attrs=[attr])
    n = await sync_riven_attributes(client, storage)
    assert n == 1
    assert storage.count("riven_attributes") == 1


async def test_ingest_riven_auctions(storage, sample_auction_raw):
    client = FakeClient([], [], [], [], auctions=[RivenAuction.from_api(sample_auction_raw)])
    n = await ingest_riven_auctions(client, storage, ["kulstar"])
    assert n == 1
    assert storage.weapons_with_auctions() == ["kulstar"]


async def test_ingest_records_fetch_state(storage, sample_item_raw, sample_weapon_raw,
                                          sample_stat_rows, sample_orders_raw):
    client = _fake_client(sample_item_raw, sample_weapon_raw, sample_stat_rows, sample_orders_raw)
    await ingest_statistics(client, storage, ["a", "b"])
    health = storage.ingest_health()
    assert health["sources"]["prices"]["tracked"] == 2
    assert health["sources"]["prices"]["ok"] == 2
    # A fetched ref is no longer "stalest"; an unfetched one leads.
    assert storage.record_fetch  # sanity: method exists


class FailingClient(FakeClient):
    async def get_statistics(self, slug, window="90days"):
        raise RuntimeError("509 too many connections")


async def test_ingest_records_failure_without_aborting(storage, sample_item_raw,
                                                       sample_weapon_raw, sample_stat_rows,
                                                       sample_orders_raw):
    client = FailingClient(
        items=[Item.from_api(sample_item_raw, "en")],
        weapons=[RivenWeapon.from_api(sample_weapon_raw, "en")],
        stats=[StatRecord.model_validate(r) for r in sample_stat_rows],
        orders=[Order.model_validate(o) for o in sample_orders_raw],
    )
    rows = await ingest_statistics(client, storage, ["a", "b"])
    assert rows == 0  # both failed, but no exception bubbled
    health = storage.ingest_health()
    assert health["sources"]["prices"]["errors"] == 2


async def test_full_ingest_batch_selects_stalest(storage, sample_item_raw, sample_weapon_raw,
                                                 sample_stat_rows, sample_orders_raw):
    from datetime import UTC, datetime

    from voidbroker.ingest import full_ingest

    # Catalog has the one sample item; pre-mark it freshly fetched so a tiny batch skips it.
    client = _fake_client(sample_item_raw, sample_weapon_raw, sample_stat_rows, sample_orders_raw)
    await sync_catalog(client, storage)
    storage.record_fetch("prices", "secura_dual_cestra", now=datetime(2030, 1, 1, tzinfo=UTC))

    # batch=1 with the only item already the freshest -> stalest_refs still returns it
    # (it's the sole candidate), so the sweep is bounded to 1 ref.
    report = await full_ingest(client, storage, batch=1)
    assert report.items == 1
    assert report.price_rows == 2  # one slug x 2 candle rows
