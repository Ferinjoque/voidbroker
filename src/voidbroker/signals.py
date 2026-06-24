"""Trade signals derived from the archive — pure functions, no I/O.

Two signals ship in Phase 2:

* **Opportunities** — items whose best *live* sell price sits below their recent price
  baseline, ranked by a liquidity-adjusted score so a fat margin on something that never
  trades doesn't outrank a thinner margin that flips in a day.
* **Disposition changes** — concrete moves in a riven weapon's disposition over time,
  the raw events the predictor will eventually learn to anticipate.

The scoring weights are deliberate, documented heuristics (v1). They're meant to be
recalibrated against realized flips once the archive has history.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Daily volume at which an item is considered fully liquid for scoring purposes.
_LIQUIDITY_SATURATION = 50.0
# Clamp flip-time estimates to a sane range (days).
_FLIP_DAYS_MIN = 0.1
_FLIP_DAYS_MAX = 60.0


def liquidity_factor(recent_volume: float | None) -> float:
    """Map average daily volume to a 0..1 liquidity multiplier (saturating)."""
    if not recent_volume or recent_volume <= 0:
        return 0.0
    return 1.0 - math.exp(-recent_volume / _LIQUIDITY_SATURATION)


def estimate_flip_days(n_sell_live: int | None, recent_volume: float | None) -> float:
    """Rough expected days to sell one unit listed competitively.

    Approximated by queue depth over throughput: you sit behind the current live sellers
    and clear at roughly the daily trade rate.
    """
    volume = recent_volume or 0.0
    if volume <= 0:
        return _FLIP_DAYS_MAX
    depth = (n_sell_live or 0) + 1
    return max(_FLIP_DAYS_MIN, min(_FLIP_DAYS_MAX, depth / volume))


@dataclass(frozen=True)
class Opportunity:
    slug: str
    name: str | None
    sell_min: float
    baseline: float
    margin: float          # baseline - sell_min (platinum)
    margin_pct: float      # margin / baseline
    liquidity: float       # recent avg daily volume
    flip_days_est: float
    score: float
    spark: list[float]     # recent daily closes, for an inline sparkline
    thumb: str | None = None  # item thumbnail (relative CDN path)


def score_opportunity(row: dict, min_margin_pct: float = 0.05) -> Opportunity | None:
    """Score one item's order-book + price-baseline inputs into an Opportunity.

    Returns None when the data is insufficient or the item isn't underpriced enough to
    bother with. ``row`` keys: sell_min, baseline_moving_avg, baseline_median,
    recent_volume, n_sell_live.
    """
    sell_min = row.get("sell_min")
    baseline = row.get("baseline_moving_avg") or row.get("baseline_median")
    if not sell_min or not baseline or baseline <= 0:
        return None

    margin = baseline - sell_min
    margin_pct = margin / baseline
    if margin_pct < min_margin_pct:
        return None

    liq = liquidity_factor(row.get("recent_volume"))
    flip_days = estimate_flip_days(row.get("n_sell_live"), row.get("recent_volume"))

    # Reward margin and liquidity; discount slow flips. Capital that turns over twice as
    # fast at the same margin is twice as good.
    score = margin_pct * liq / (1.0 + flip_days)

    return Opportunity(
        slug=row["slug"],
        name=row.get("name"),
        sell_min=sell_min,
        baseline=round(baseline, 2),
        margin=round(margin, 2),
        margin_pct=round(margin_pct, 4),
        liquidity=round(row.get("recent_volume") or 0.0, 2),
        flip_days_est=round(flip_days, 2),
        score=round(score, 5),
        spark=[round(c, 2) for c in (row.get("spark") or [])],
        thumb=row.get("thumb"),
    )


def rank_opportunities(rows: list[dict], min_margin_pct: float = 0.05) -> list[Opportunity]:
    scored = (score_opportunity(r, min_margin_pct) for r in rows)
    found = [o for o in scored if o is not None]
    return sorted(found, key=lambda o: o.score, reverse=True)


@dataclass(frozen=True)
class DispositionChange:
    slug: str
    from_disposition: float
    to_disposition: float
    delta: float
    direction: str  # "buff" | "nerf"
    at: object      # captured_at timestamp of the new value


def detect_disposition_changes(slug: str, history: list[dict]) -> list[DispositionChange]:
    """Find points where disposition actually moved between consecutive snapshots.

    ``history`` is ascending rows of ``{captured_at, disposition}``. A rise is a *buff*
    (rivens get stronger / more valuable); a fall is a *nerf*.
    """
    changes: list[DispositionChange] = []
    prev: float | None = None
    for row in history:
        disp = row.get("disposition")
        if disp is None:
            continue
        if prev is not None and disp != prev:
            changes.append(
                DispositionChange(
                    slug=slug,
                    from_disposition=prev,
                    to_disposition=disp,
                    delta=round(disp - prev, 4),
                    direction="buff" if disp > prev else "nerf",
                    at=row.get("captured_at"),
                )
            )
        prev = disp
    return changes
