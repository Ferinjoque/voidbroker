from __future__ import annotations

from datetime import UTC, datetime

from voidbroker.metrics import aggregate_orders
from voidbroker.models import Item, Order, RivenWeapon, StatRecord


def test_upsert_items_is_idempotent(storage, sample_item_raw):
    item = Item.from_api(sample_item_raw, "en")
    storage.upsert_items([item])
    storage.upsert_items([item])  # again
    assert storage.count("items") == 1


def test_table_counts_matches_individual_counts(storage, sample_item_raw, sample_weapon_raw):
    storage.upsert_items([Item.from_api(sample_item_raw, "en")])
    storage.upsert_riven_weapons([RivenWeapon.from_api(sample_weapon_raw, "en")])
    counts = storage.table_counts("items", "riven_weapons", "price_history")
    assert counts == {
        "items": storage.count("items"),
        "riven_weapons": storage.count("riven_weapons"),
        "price_history": storage.count("price_history"),
    }


def test_table_counts_rejects_unknown_table(storage):
    import pytest

    with pytest.raises(ValueError):
        storage.table_counts("items", "definitely_not_a_table")


def test_riven_weapon_upsert_records_disposition_snapshots(storage, sample_weapon_raw):
    w = RivenWeapon.from_api(sample_weapon_raw, "en")
    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    t2 = datetime(2026, 3, 1, tzinfo=UTC)

    storage.upsert_riven_weapons([w], now=t1)
    w2 = w.model_copy(update={"disposition": 1.1})  # disposition nerfed
    storage.upsert_riven_weapons([w2], now=t2)

    assert storage.count("riven_weapons") == 1  # metadata deduped
    history = storage.disposition_history("kulstar")
    assert len(history) == 2
    assert [h["disposition"] for h in history] == [1.3, 1.1]


def test_price_history_upsert_and_read(storage, sample_stat_rows):
    records = [StatRecord.model_validate(r) for r in sample_stat_rows]
    written = storage.upsert_price_history("mirage_prime_set", records)
    assert written == 2

    # Re-upsert same days should not duplicate.
    storage.upsert_price_history("mirage_prime_set", records)
    series = storage.price_series("mirage_prime_set")
    assert len(series) == 2
    assert series[0]["volume"] == 137


def test_order_snapshot_roundtrip(storage, sample_orders_raw):
    orders = [Order.model_validate(o) for o in sample_orders_raw]
    storage.record_order_snapshot("foo", aggregate_orders(orders))
    snap = storage.latest_order_snapshot("foo")
    assert snap["sell_min"] == 90
    assert snap["spread"] == 20


def test_top_by_volume(storage, sample_stat_rows):
    records = [StatRecord.model_validate(r) for r in sample_stat_rows]
    storage.upsert_price_history("a", records)
    storage.upsert_price_history("b", records[:1])  # only the 137-volume day
    top = storage.top_by_volume(limit=5)
    assert top[0]["volume"] >= top[-1]["volume"]
    # Each row carries a recent-close sparkline series.
    assert isinstance(top[0]["spark"], list) and len(top[0]["spark"]) >= 1


def test_opportunity_inputs_joins_orderbook_and_baseline(storage, sample_stat_rows,
                                                         sample_orders_raw):
    records = [StatRecord.model_validate(r) for r in sample_stat_rows]
    storage.upsert_price_history("x", records)
    storage.record_order_snapshot("x", aggregate_orders(
        [Order.model_validate(o) for o in sample_orders_raw]
    ))
    # An item with price history but no order snapshot must NOT appear.
    storage.upsert_price_history("no_orders", records)

    rows = storage.opportunity_inputs(baseline_days=30)
    assert len(rows) == 1
    row = rows[0]
    assert row["slug"] == "x"
    assert row["sell_min"] == 90
    assert row["baseline_moving_avg"] == 86.4  # last moving_avg by datetime
    assert row["recent_volume"] == (137 + 134) / 2
    assert row["spark"] == [80, 88]  # recent closes in datetime order


def test_riven_attributes_upsert_idempotent(storage, sample_riven_attr_raw):
    from voidbroker.models import RivenAttribute

    attr = RivenAttribute.from_api(sample_riven_attr_raw, "en")
    storage.upsert_riven_attributes([attr])
    storage.upsert_riven_attributes([attr])
    assert storage.count("riven_attributes") == 1


def test_riven_auction_roundtrip_reconstructs_model(storage, sample_auction_raw):
    from voidbroker.models import RivenAuction

    auction = RivenAuction.from_api(sample_auction_raw)
    storage.record_riven_auctions("kulstar", [auction])

    assert storage.weapons_with_auctions() == ["kulstar"]
    rebuilt = storage.latest_riven_auctions("kulstar")
    assert len(rebuilt) == 1
    a = rebuilt[0]
    assert a.id == "684b0f8fe3a05e0037564679"
    assert a.buyout_price == 40
    assert a.owner_status == "ingame"
    assert {s.url_name for s in a.attributes} == {"zoom", "impact_damage"}
    assert a.is_live is True


def test_trade_log_record_list_delete(storage):
    t1 = storage.record_trade("x_prime_set", "buy", 2, 50, note="cheap")
    t2 = storage.record_trade("x_prime_set", "sell", 1, 80)
    assert t1 != t2  # sequence ids
    trades = storage.list_trades()
    assert [t["side"] for t in trades] == ["buy", "sell"]
    assert trades[0]["quantity"] == 2 and trades[0]["note"] == "cheap"
    assert storage.delete_trade(t1) is True
    assert storage.delete_trade(99999) is False
    assert len(storage.list_trades()) == 1


def test_alert_dedup_window(storage):
    from datetime import UTC, datetime

    from voidbroker.alerts import Alert
    now = datetime(2026, 6, 23, 12, tzinfo=UTC)
    storage.record_alerts([Alert("opportunity", "opp:a", "A", "d")], now=now)
    # Within window -> seen; outside -> not.
    assert "opp:a" in storage.recent_alert_keys(18.0, now=now)
    assert "opp:a" not in storage.recent_alert_keys(
        1.0, now=datetime(2026, 6, 24, 12, tzinfo=UTC)
    )


def _price(slug, ma):
    from voidbroker.models import StatRecord
    rec = StatRecord.model_validate({
        "datetime": "2026-06-20T00:00:00.000+00:00", "volume": 10, "min_price": ma, "max_price": ma,
        "open_price": ma, "closed_price": ma, "avg_price": ma, "wa_price": ma, "median": ma,
        "moving_avg": ma, "donch_top": ma, "donch_bot": ma, "id": slug,
    })
    return rec


def test_set_arbitrage_inputs_resolves_parts_and_prices(storage):
    from voidbroker.models import Item, ItemDetail
    storage.upsert_items([
        Item(id="SET", slug="x_prime_set", name="X Prime Set", tags=["prime"]),
        Item(id="P1", slug="x_prime_blueprint", name="X Prime Blueprint", tags=["prime"]),
        Item(id="P2", slug="x_prime_systems", name="X Prime Systems", tags=["prime"]),
    ])
    storage.upsert_item_details([
        ItemDetail(slug="x_prime_set", set_root=True, set_parts=["P1", "P2"], tradable=True),
        ItemDetail(slug="x_prime_blueprint", ducats=15, tradable=True),
        ItemDetail(slug="x_prime_systems", ducats=15, tradable=True),
    ])
    storage.upsert_price_history("x_prime_set", [_price("x_prime_set", 100)])
    storage.upsert_price_history("x_prime_blueprint", [_price("x_prime_blueprint", 30)])
    storage.upsert_price_history("x_prime_systems", [_price("x_prime_systems", 25)])

    inputs = storage.set_arbitrage_inputs()
    assert len(inputs) == 1
    row = inputs[0]
    assert row["slug"] == "x_prime_set" and row["set_price"] == 100
    parts = {p["slug"]: p["price"] for p in row["parts"]}
    assert parts == {"x_prime_blueprint": 30, "x_prime_systems": 25}  # ids resolved + priced


def test_ducat_efficiency_inputs_joins_price(storage):
    from voidbroker.models import Item, ItemDetail
    storage.upsert_items([Item(id="P1", slug="x_prime_systems", name="X Prime Systems", tags=[])])
    storage.upsert_item_details([ItemDetail(slug="x_prime_systems", ducats=45, tradable=True)])
    storage.upsert_price_history("x_prime_systems", [_price("x_prime_systems", 5)])
    rows = storage.ducat_efficiency_inputs()
    assert rows == [{"slug": "x_prime_systems", "name": "X Prime Systems", "thumb": None,
                     "ducats": 45, "price": 5.0}]


def test_all_latest_riven_auctions_live_filter_uses_latest_snapshot(storage, sample_auction_raw):
    from datetime import UTC, datetime

    from voidbroker.models import RivenAuction

    base = RivenAuction.from_api(sample_auction_raw)  # owner ingame -> live
    # An auction whose OWNER went offline in its latest snapshot must be excluded, even though
    # an earlier snapshot was online (filter applies to the latest snapshot only).
    online = base.model_copy(update={"id": "went_offline", "owner_status": "online"})
    offline = base.model_copy(update={"id": "went_offline", "owner_status": "offline"})
    storage.record_riven_auctions("kulstar", [online], now=datetime(2026, 1, 1, tzinfo=UTC))
    storage.record_riven_auctions("kulstar", [offline], now=datetime(2026, 2, 1, tzinfo=UTC))
    # A currently-live auction.
    live = base.model_copy(update={"id": "live_one", "owner_status": "ingame"})
    storage.record_riven_auctions("kulstar", [live], now=datetime(2026, 2, 1, tzinfo=UTC))

    grouped = storage.all_latest_riven_auctions(live_only=True)
    ids = {a.id for a in grouped.get("kulstar", [])}
    assert "live_one" in ids
    assert "went_offline" not in ids  # latest snapshot is offline -> excluded

    # Without the filter, both auctions' latest snapshots are returned.
    all_ids = {a.id for a in storage.all_latest_riven_auctions(live_only=False).get("kulstar", [])}
    assert {"live_one", "went_offline"} <= all_ids


def test_all_disposition_histories_grouped(storage, sample_weapon_raw):
    from datetime import UTC, datetime

    w = RivenWeapon.from_api(sample_weapon_raw, "en")
    storage.upsert_riven_weapons([w], now=datetime(2026, 1, 1, tzinfo=UTC))
    w2 = w.model_copy(update={"disposition": 1.1})
    storage.upsert_riven_weapons([w2], now=datetime(2026, 3, 1, tzinfo=UTC))

    grouped = storage.all_disposition_histories()
    assert set(grouped) == {"kulstar"}
    assert [r["disposition"] for r in grouped["kulstar"]] == [1.3, 1.1]


def _seed_items(storage, slugs):
    items = [Item(id=s, slug=s, name=s.title(), tags=[]) for s in slugs]
    storage.upsert_items(items)


def test_item_thumb_roundtrips(storage, sample_item_raw):
    item = Item.from_api(sample_item_raw, "en")
    assert item.thumb and item.thumb.endswith(".png")
    storage.upsert_items([item])
    meta = storage.item_meta("secura_dual_cestra")
    assert meta["thumb"] == item.thumb
    assert storage.search_items("secura")[0]["thumb"] == item.thumb


def test_record_fetch_and_stalest_ordering(storage):
    _seed_items(storage, ["a", "b", "c"])
    t1 = datetime(2026, 1, 1, tzinfo=UTC)
    t2 = datetime(2026, 2, 1, tzinfo=UTC)
    # 'a' fetched oldest, 'b' fetched recently, 'c' never fetched.
    storage.record_fetch("prices", "a", ok=True, now=t1)
    storage.record_fetch("prices", "b", ok=True, now=t2)

    # Never-fetched first, then oldest-fetched. 'c' (None) leads, then 'a', then 'b'.
    assert storage.stalest_refs("prices", 3) == ["c", "a", "b"]
    assert storage.stalest_refs("prices", 1) == ["c"]


def test_record_fetch_upserts_outcome(storage):
    _seed_items(storage, ["a"])
    storage.record_fetch("orders", "a", ok=True, now=datetime(2026, 1, 1, tzinfo=UTC))
    storage.record_fetch(
        "orders", "a", ok=False, error="boom", now=datetime(2026, 2, 1, tzinfo=UTC)
    )
    health = storage.ingest_health()
    assert health["sources"]["orders"]["tracked"] == 1
    assert health["sources"]["orders"]["errors"] == 1
    assert health["sources"]["orders"]["ok"] == 0


def test_stalest_refs_rejects_unknown_source(storage):
    import pytest

    with pytest.raises(ValueError):
        storage.stalest_refs("nonsense", 5)


def test_ingest_health_coverage(storage, sample_weapon_raw):
    _seed_items(storage, ["a", "b", "c", "d"])
    storage.upsert_riven_weapons([RivenWeapon.from_api(sample_weapon_raw, "en")])
    storage.record_fetch("prices", "a")
    storage.record_fetch("prices", "b")

    health = storage.ingest_health()
    assert health["catalog"]["items"] == 4
    prices = health["sources"]["prices"]
    assert prices["catalog"] == 4 and prices["tracked"] == 2
    assert prices["coverage_pct"] == 50.0
    # Auctions track against the weapon catalog (1 weapon, none fetched yet).
    assert health["sources"]["auctions"]["catalog"] == 1
    assert health["sources"]["auctions"]["tracked"] == 0
