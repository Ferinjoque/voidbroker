"""Pure analytical functions — no I/O, so they're trivially unit-testable.

This is where order-book aggregation lives now, and where liquidity scoring and the
fair-value / disposition models will grow later.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import Order


def percentile(sorted_values: list[float], q: float) -> float | None:
    """Linear-interpolated percentile of an already-sorted ascending list."""
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


@dataclass(frozen=True)
class OrderBookSnapshot:
    """Aggregated, point-in-time view of one item's order book."""

    sell_min: float | None
    sell_p25: float | None
    sell_median: float | None
    buy_max: float | None
    spread: float | None
    n_sell_live: int
    n_buy_live: int
    n_sell_total: int
    n_buy_total: int


def aggregate_orders(orders: list[Order]) -> OrderBookSnapshot:
    """Collapse a raw order list into a storable snapshot.

    Headline prices use only *live* orders (sellers/buyers who are online or in-game),
    because an offline listing from 2017 is not a real, fillable price. Totals are kept
    separately as a depth/interest signal.
    """
    sells = [o for o in orders if o.type == "sell"]
    buys = [o for o in orders if o.type == "buy"]

    live_sell_prices = sorted(o.platinum for o in sells if o.is_live)
    live_buy_prices = sorted((o.platinum for o in buys if o.is_live), reverse=True)

    sell_min = live_sell_prices[0] if live_sell_prices else None
    buy_max = live_buy_prices[0] if live_buy_prices else None
    spread = (sell_min - buy_max) if (sell_min is not None and buy_max is not None) else None

    return OrderBookSnapshot(
        sell_min=sell_min,
        sell_p25=percentile(live_sell_prices, 0.25),
        sell_median=percentile(live_sell_prices, 0.50),
        buy_max=buy_max,
        spread=spread,
        n_sell_live=len(live_sell_prices),
        n_buy_live=len(live_buy_prices),
        n_sell_total=len(sells),
        n_buy_total=len(buys),
    )
