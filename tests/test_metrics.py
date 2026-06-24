from __future__ import annotations

from voidbroker.metrics import aggregate_orders, percentile
from voidbroker.models import Order


def test_percentile_basics():
    assert percentile([], 0.5) is None
    assert percentile([42], 0.5) == 42
    assert percentile([0, 10], 0.5) == 5
    assert percentile([0, 10, 20, 30], 0.25) == 7.5


def test_aggregate_uses_only_live_orders_for_headline_prices(sample_orders_raw):
    orders = [Order.model_validate(o) for o in sample_orders_raw]
    snap = aggregate_orders(orders)

    # Cheapest LIVE sell is 90 (the 50 offline order is excluded from headline).
    assert snap.sell_min == 90
    assert snap.buy_max == 70
    assert snap.spread == 20  # 90 - 70

    assert snap.n_sell_live == 2
    assert snap.n_buy_live == 1
    assert snap.n_sell_total == 3
    assert snap.n_buy_total == 2


def test_aggregate_empty_orderbook():
    snap = aggregate_orders([])
    assert snap.sell_min is None
    assert snap.spread is None
    assert snap.n_sell_total == 0
