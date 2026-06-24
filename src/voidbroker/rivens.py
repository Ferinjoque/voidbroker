"""Riven valuation — comparables-based appraisal and the undervalued-listing scanner.

Rivens are unique randomized items, so there's no single "price." But auctions for the
*same weapon with the same attribute signature* (same set of positive/negative stats) are
genuine comparables. We group live auctions by signature, take the median asking price per
group, and flag listings priced well below their comparables — a god-roll mispriced like
junk. This is data-driven and works today; an ML model can refine it once auction history
accumulates.
"""

from __future__ import annotations

import bisect
from collections import defaultdict
from dataclasses import dataclass
from statistics import fmean, median

from .models import RivenAuction

# Index of a comparable group's stat values: (url_name, positive) -> sorted values.
StatIndex = dict[tuple[str, bool], list[float]]


def attribute_signature(auction: RivenAuction, positives_only: bool = False) -> str:
    """A canonical key for an auction's stat layout: sorted positives, then negatives.

    Two rivens with the same signature are comparables regardless of exact roll values,
    e.g. ``+crit_damage,multishot|-zoom``. Roll *values* refine price within a group; the
    signature defines the group.

    ``positives_only=True`` groups on the positive stats alone (negatives collapse to a
    has/hasn't flag). Exact-negative matching fragments liquidity — most builds care far
    more about the positives — so the looser key surfaces comparables for the scanner while
    the strict key stays available for precise appraisal.
    """
    pos = sorted(a.url_name for a in auction.attributes if a.positive)
    if positives_only:
        has_neg = any(not a.positive for a in auction.attributes)
        return "+" + ",".join(pos) + ("|+neg" if has_neg else "|noneg")
    neg = sorted(a.url_name for a in auction.attributes if not a.positive)
    return "+" + ",".join(pos) + "|-" + ",".join(neg)


def effective_price(auction: RivenAuction) -> float | None:
    """The price a buyer would actually pay / the seller signals.

    Direct-sell auctions use buyout. Otherwise prefer the current top bid, then buyout,
    then the starting price.
    """
    if auction.is_direct_sell and auction.buyout_price:
        return auction.buyout_price
    return auction.top_bid or auction.buyout_price or auction.starting_price


def _percentile(sorted_values: list[float], x: float) -> float:
    """Fraction of ``sorted_values`` at or below ``x`` (0..1). A lone value is neutral (0.5).

    ``sorted_values`` MUST be sorted ascending; uses binary search (O(log n)).
    """
    n = len(sorted_values)
    if n <= 1:
        return 0.5
    below = bisect.bisect_left(sorted_values, x)
    equal = bisect.bisect_right(sorted_values, x) - below
    return (below + 0.5 * equal) / n


def build_stat_index(group: list[RivenAuction]) -> StatIndex:
    """Precompute each stat's sorted value list across a comparable group, ONCE.

    Negatives are indexed by magnitude (abs). Done once per group so per-auction roll
    scoring is O(log n) lookups instead of rescanning the whole group per stat (was O(n²)).
    """
    index: StatIndex = defaultdict(list)
    for auction in group:
        for attr in auction.attributes:
            value = attr.value if attr.positive else abs(attr.value)
            index[(attr.url_name, attr.positive)].append(value)
    for values in index.values():
        values.sort()
    return index


def roll_quality(
    auction: RivenAuction, group: list[RivenAuction], stat_index: StatIndex | None = None
) -> float:
    """How strong this auction's roll is *relative to its comparables* (0..1).

    Raw stat values aren't comparable across stats (crit damage vs. multishot), but within a
    signature group the same stats recur, so each value is percentile-ranked against the
    group's values for that same stat. Positives reward high values; a negative rewards a
    *milder* magnitude. Positives dominate (0.8) since that's what builds care about. This is
    what separates a genuine underpriced god-roll from a cheap weak roll.

    Pass ``stat_index`` (from ``build_stat_index``) to score a whole group cheaply; it's
    built once per group instead of rescanned per auction.
    """
    index = stat_index if stat_index is not None else build_stat_index(group)
    pos = [a for a in auction.attributes if a.positive]
    neg = [a for a in auction.attributes if not a.positive]

    pos_scores = [
        _percentile(index.get((st.url_name, True), [st.value]), st.value) for st in pos
    ]
    neg_scores = [
        1.0 - _percentile(index.get((st.url_name, False), [abs(st.value)]), abs(st.value))
        for st in neg
    ]
    pos_q = fmean(pos_scores) if pos_scores else 0.5
    neg_q = fmean(neg_scores) if neg_scores else 1.0  # no negative is best
    return round(0.8 * pos_q + 0.2 * neg_q, 4)


def quality_label(q: float) -> str:
    if q >= 0.75:
        return "strong"
    if q >= 0.55:
        return "above avg"
    if q >= 0.4:
        return "average"
    return "weak"


@dataclass(frozen=True)
class Comparable:
    signature: str
    count: int
    median_price: float
    floor_price: float


def appraise(auctions: list[RivenAuction], positives_only: bool = False) -> dict[str, Comparable]:
    """Group live auctions by signature and summarize the price of each group."""
    groups: dict[str, list[float]] = {}
    for a in auctions:
        if not a.is_live:
            continue
        price = effective_price(a)
        if price is None or price <= 0:
            continue
        groups.setdefault(attribute_signature(a, positives_only), []).append(price)

    result: dict[str, Comparable] = {}
    for sig, prices in groups.items():
        prices.sort()
        result[sig] = Comparable(
            signature=sig,
            count=len(prices),
            median_price=median(prices),
            floor_price=prices[0],
        )
    return result


@dataclass(frozen=True)
class RivenDeal:
    auction_id: str
    weapon_slug: str
    signature: str
    price: float
    comparable_median: float
    discount_pct: float       # how far below the comparable median, 0..1
    comparable_count: int
    owner_status: str
    roll_quality: float       # 0..1 vs comparables; separates god-rolls from weak rolls
    roll_label: str           # "strong" | "above avg" | "average" | "weak"
    score: float              # discount × confidence × roll quality


def find_undervalued(
    weapon_slug: str,
    auctions: list[RivenAuction],
    min_comparables: int = 4,
    min_discount: float = 0.25,
    positives_only: bool = False,
) -> list[RivenDeal]:
    """Flag live auctions priced below their comparable group's median.

    Requires a minimum group size so a "deal" is judged against real liquidity, not one
    lonely listing. Returns deals ranked by a score that rewards both depth of discount and
    comparable confidence.
    """
    comps = appraise(auctions, positives_only=positives_only)

    # Live auctions grouped by signature, so roll quality is judged against the same peers
    # the median price came from. Each group's stat index is built once (not per auction).
    groups: dict[str, list[RivenAuction]] = {}
    for a in auctions:
        if a.is_live and (effective_price(a) or 0) > 0:
            groups.setdefault(attribute_signature(a, positives_only), []).append(a)
    stat_indexes = {sig: build_stat_index(g) for sig, g in groups.items()}

    deals: list[RivenDeal] = []
    for a in auctions:
        if not a.is_live:
            continue
        price = effective_price(a)
        if price is None or price <= 0:
            continue
        sig = attribute_signature(a, positives_only)
        comp = comps.get(sig)
        if comp is None or comp.count < min_comparables:
            continue

        discount = 1.0 - (price / comp.median_price)
        if discount < min_discount:
            continue

        # Confidence rises with group size but saturates; a 50%-off in a 20-deep group
        # beats a 50%-off in a 4-deep group.
        confidence = min(1.0, comp.count / 15.0)
        quality = roll_quality(a, groups.get(sig, [a]), stat_indexes.get(sig))
        # A weak roll is *supposed* to be cheap, so it isn't a deal. Quality scales the
        # score (floored so a great-discount average roll still surfaces).
        quality_factor = 0.4 + 0.6 * quality
        deals.append(
            RivenDeal(
                auction_id=a.id,
                weapon_slug=weapon_slug,
                signature=sig,
                price=round(price, 2),
                comparable_median=round(comp.median_price, 2),
                discount_pct=round(discount, 4),
                comparable_count=comp.count,
                owner_status=a.owner_status,
                roll_quality=quality,
                roll_label=quality_label(quality),
                score=round(discount * confidence * quality_factor, 5),
            )
        )

    return sorted(deals, key=lambda d: d.score, reverse=True)
