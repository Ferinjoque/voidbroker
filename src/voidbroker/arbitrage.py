"""Set-vs-parts arbitrage and ducat efficiency, pure functions, no I/O.

Two classic Warframe economy plays that are tedious to track by hand but trivial once the
catalog's ducat values and set compositions are archived:

* **Set arbitrage**, a Prime "set" trades as one listing, but it's really its component
  parts. When the set price and the summed part prices diverge, there's a flip: buy the
  parts and sell the assembled set ("build"), or buy the set and relist the parts
  individually ("split"). We only trust a spread when *every* part has a price.
* **Ducat efficiency**, every item has a fixed ducat value (what Baro pays). Ranking parts
  by ducats-per-platinum surfaces the cheapest way to convert plat into ducats for Baro.

Prices are caller-supplied (the storage layer joins the latest market price); these
functions just do the arithmetic and ranking.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SetArbitrage:
    slug: str
    name: str | None
    set_price: float
    parts_cost: float        # summed price of all component parts
    n_parts: int
    direction: str           # "build" (buy parts, sell set) | "split" (buy set, sell parts)
    profit: float            # gross plat spread (before the credit trade tax)
    margin_pct: float        # profit / cost of the side you buy


def set_arbitrage(
    sets: list[dict],
    min_margin: float = 0.10,
    min_parts: int = 2,
    max_margin: float = 1.5,
    min_profit: float = 8.0,
) -> list[SetArbitrage]:
    """Flag sets whose price diverges from the summed cost of their parts.

    Each ``sets`` row: ``{slug, name, set_price, parts: [{slug, name, price}]}``. A set is
    only scored when it has >= ``min_parts`` parts and *every* part is priced (otherwise the
    spread is untrustworthy). Returns flips with margin in [``min_margin``, ``max_margin``]
    *and* at least ``min_profit`` plat of absolute profit (cheap sets show huge percentages on
    a few plat of profit), ranked by margin. ``max_margin`` discards implausible spreads, a
    real set arbitrage over ~150% would already have been taken; it's a stale/illiquid price.
    """
    out: list[SetArbitrage] = []
    for s in sets:
        parts = s.get("parts") or []
        set_price = s.get("set_price")
        if not set_price or len(parts) < min_parts:
            continue
        if any(p.get("price") is None for p in parts):
            continue  # incomplete pricing -> can't trust the spread
        parts_cost = round(sum(p["price"] for p in parts), 2)
        if parts_cost <= 0:
            continue

        spread = set_price - parts_cost
        if spread >= 0:
            direction, cost, profit = "build", parts_cost, spread  # buy parts -> sell set
        else:
            direction, cost, profit = "split", set_price, -spread  # buy set -> sell parts
        margin = profit / cost if cost else 0.0
        if margin < min_margin or margin > max_margin or profit < min_profit:
            continue

        out.append(
            SetArbitrage(
                slug=s["slug"],
                name=s.get("name"),
                set_price=round(set_price, 2),
                parts_cost=parts_cost,
                n_parts=len(parts),
                direction=direction,
                profit=round(profit, 2),
                margin_pct=round(margin, 4),
            )
        )
    return sorted(out, key=lambda a: a.margin_pct, reverse=True)


@dataclass(frozen=True)
class DucatDeal:
    slug: str
    name: str | None
    thumb: str | None
    ducats: int
    price: float
    ducats_per_plat: float


def rank_ducat_efficiency(
    items: list[dict], min_ducats: int = 15, min_price: float = 1.0
) -> list[DucatDeal]:
    """Rank items by ducats per platinum, the cheapest plat→ducat conversion for Baro prep.

    Each ``items`` row: ``{slug, name, thumb, ducats, price}``. Filters out trivial-ducat
    items and sub-1p noise (where the ratio explodes on rounding). Ranked best ratio first.
    """
    out: list[DucatDeal] = []
    for it in items:
        price = it.get("price") or 0.0
        ducats = it.get("ducats") or 0
        if price < min_price or ducats < min_ducats:
            continue
        out.append(
            DucatDeal(
                slug=it["slug"],
                name=it.get("name"),
                thumb=it.get("thumb"),
                ducats=ducats,
                price=round(price, 2),
                ducats_per_plat=round(ducats / price, 2),
            )
        )
    return sorted(out, key=lambda d: d.ducats_per_plat, reverse=True)
