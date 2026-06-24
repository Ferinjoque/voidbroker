"""Riven disposition prediction — the headline signal, pure functions, no I/O.

Digital Extremes sets each weapon's *riven disposition* inversely to how much the
weapon is used: heavily-used weapons get a low disposition (weaker rivens), neglected
weapons get a high one (stronger rivens to coax people into using them). DE rebalances
periodically. warframe.market exposes only the *current* disposition and no history, so
nobody can see the trajectory — voidbroker snapshots it forever, which is what makes a
forward-looking call possible at all.

The forecast combines three forces into one signed ``pressure`` score where
**positive = buff (disposition likely to rise)** and **negative = nerf (likely to fall)**:

1. **Mean reversion** — disposition is bounded and balances around a nominal 1.0. A value
   far above nominal is more likely to be cut; far below, more likely to be raised.
2. **Demand pressure** — riven auction activity (how many people sell rivens for this
   weapon, and at what price) is a proxy for in-game usage. Strong demand is exactly the
   usage signal DE nerfs; weak demand invites a buff.
3. **Momentum** — the recent slope of archived disposition. Early on this is silent (not
   enough snapshots) and contributes nothing; it sharpens as the archive compounds.

These weights are deliberate, documented heuristics (v1), meant to be recalibrated against
realized disposition changes once the archive has logged a few DE rebalances.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Any

# Disposition is quantized to a 0.5..1.55 numeric range on warframe.market, balanced
# around a nominal 1.0 ("average usage"). Reversion is measured against the nominal.
_DISP_FLOOR = 0.5
_DISP_CEIL = 1.55
_DISP_NOMINAL = 1.0
_DISP_HALF_SPAN = max(_DISP_CEIL - _DISP_NOMINAL, _DISP_NOMINAL - _DISP_FLOOR)  # 0.55

# Demand saturation: where the auction-count and price terms reach ~63% of their max.
_DEMAND_COUNT_SAT = 15.0
_DEMAND_PRICE_SAT = 400.0

# A disposition delta this small (numeric) is treated as noise, not a real move.
_MOMENTUM_EPS = 1e-6


@dataclass(frozen=True)
class ForecastConfig:
    """Tunable weights and thresholds for the v1 heuristic. Weights are renormalized to
    whatever components actually have data, so a missing demand proxy never silently
    deflates the score, it just shifts emphasis onto the others."""

    w_reversion: float = 0.45
    w_demand: float = 0.35
    w_momentum: float = 0.20
    # |pressure| below this reads as "stable" rather than a directional call.
    direction_threshold: float = 0.15


DEFAULT_CONFIG = ForecastConfig()


@dataclass(frozen=True)
class DispositionForecast:
    slug: str
    name: str | None
    current_disposition: float
    direction: str          # "buff" | "nerf" | "stable"
    pressure: float         # signed, [-1, 1]; + = buff pressure, - = nerf pressure
    confidence: float       # [0, 1]
    reasons: list[str] = field(default_factory=list)
    n_history: int = 0      # disposition snapshots informing momentum
    demand: float | None = None  # normalized demand proxy [0, 1], None if unknown


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def reversion_pressure(current: float) -> float:
    """Signed pull back toward nominal disposition. +1 floor, -1 ceiling, 0 at nominal."""
    return _clamp((_DISP_NOMINAL - current) / _DISP_HALF_SPAN)


def demand_norm(n_auctions: int | None, median_price: float | None) -> float | None:
    """Blend auction count and price level into a 0..1 demand proxy (saturating).

    Returns None when there's no auction data at all, so the caller can drop the demand
    term instead of treating "unknown" as "no demand".
    """
    if not n_auctions and not median_price:
        return None
    count_term = 1.0 - math.exp(-(n_auctions or 0) / _DEMAND_COUNT_SAT)
    price_term = 1.0 - math.exp(-(median_price or 0.0) / _DEMAND_PRICE_SAT)
    return _clamp(0.5 * count_term + 0.5 * price_term, 0.0, 1.0)


def demand_pressure(demand: float | None) -> float | None:
    """Map demand (0..1) to signed pressure: high demand -> nerf (-), low demand -> buff (+)."""
    if demand is None:
        return None
    return _clamp((0.5 - demand) * 2.0)


def momentum_pressure(history: list[dict]) -> float | None:
    """Signed recent trend in disposition: rising -> + (buff continues), falling -> -.

    Uses the net move from the earliest to the latest of the most recent few snapshots,
    normalized by the disposition span. Returns None with fewer than two real points.
    """
    values = [r["disposition"] for r in history if r.get("disposition") is not None]
    if len(values) < 2:
        return None
    recent = values[-4:]
    delta = recent[-1] - recent[0]
    if abs(delta) < _MOMENTUM_EPS:
        return 0.0
    return _clamp(delta / _DISP_HALF_SPAN)


def forecast_disposition(
    slug: str,
    name: str | None,
    current_disposition: float,
    history: list[dict] | None = None,
    n_auctions: int | None = None,
    median_price: float | None = None,
    *,
    config: ForecastConfig = DEFAULT_CONFIG,
) -> DispositionForecast:
    """Produce a directional disposition forecast for one weapon.

    ``history`` is ascending rows of ``{captured_at, disposition}`` (the archive's own
    snapshots). ``n_auctions`` / ``median_price`` summarize current riven auction demand.
    Any of the three may be absent; the present components are reweighted to sum to 1 and
    confidence is scaled down to reflect the thinner evidence.
    """
    history = history or []
    dem = demand_norm(n_auctions, median_price)

    components = {
        "reversion": (config.w_reversion, reversion_pressure(current_disposition)),
        "demand": (config.w_demand, demand_pressure(dem)),
        "momentum": (config.w_momentum, momentum_pressure(history)),
    }
    present = {k: (w, v) for k, (w, v) in components.items() if v is not None}
    total_w = sum(w for w, _ in present.values()) or 1.0
    pressure = _clamp(sum(w * v for w, v in present.values()) / total_w)

    if pressure > config.direction_threshold:
        direction = "buff"
    elif pressure < -config.direction_threshold:
        direction = "nerf"
    else:
        direction = "stable"

    # Confidence: how strong the signal is, scaled by how much of the model had data.
    # A full-evidence forecast can reach 1.0; a reversion-only one is capped well below.
    coverage = total_w / (config.w_reversion + config.w_demand + config.w_momentum)
    confidence = round(_clamp(abs(pressure) * coverage, 0.0, 1.0), 3)

    return DispositionForecast(
        slug=slug,
        name=name,
        current_disposition=round(current_disposition, 3),
        direction=direction,
        pressure=round(pressure, 4),
        confidence=confidence,
        reasons=_explain(current_disposition, dem, n_auctions, median_price, history, direction),
        n_history=len([r for r in history if r.get("disposition") is not None]),
        demand=None if dem is None else round(dem, 3),
    )


def _explain(
    current: float,
    dem: float | None,
    n_auctions: int | None,
    median_price: float | None,
    history: list[dict],
    direction: str,
) -> list[str]:
    """Human-readable rationale, one line per force that meaningfully fired."""
    reasons: list[str] = []

    if current >= _DISP_NOMINAL + 0.15:
        reasons.append(
            f"Disposition {current:.2f} sits well above the {_DISP_NOMINAL:.1f} baseline; "
            "high dispositions are the ones DE tends to cut."
        )
    elif current <= _DISP_NOMINAL - 0.15:
        reasons.append(
            f"Disposition {current:.2f} sits below the {_DISP_NOMINAL:.1f} baseline; "
            "low dispositions are candidates for a buff."
        )
    else:
        reasons.append(f"Disposition {current:.2f} is near the {_DISP_NOMINAL:.1f} baseline.")

    if dem is not None:
        bits = []
        if n_auctions:
            bits.append(f"{n_auctions} active auction{'s' if n_auctions != 1 else ''}")
        if median_price:
            bits.append(f"median buyout {median_price:.0f}p")
        detail = f" ({', '.join(bits)})" if bits else ""
        if dem >= 0.6:
            reasons.append(
                f"Riven demand is strong{detail}, a usage signal DE tends to answer with a nerf."
            )
        elif dem <= 0.3:
            reasons.append(
                f"Riven demand is thin{detail}, leaving room for a disposition buff."
            )
        else:
            reasons.append(f"Riven demand is moderate{detail}.")
    else:
        reasons.append("No riven auction data yet; demand pressure is unmeasured.")

    n_pts = len([r for r in history if r.get("disposition") is not None])
    if n_pts >= 2:
        mom = momentum_pressure(history)
        span = min(n_pts, 4)
        if mom and mom > 0.02:
            reasons.append(f"Archived disposition has drifted up over the last {span} snapshots.")
        elif mom and mom < -0.02:
            reasons.append(f"Archived disposition has drifted down over the last {span} snapshots.")
        else:
            reasons.append(f"Archived disposition has held steady across {n_pts} snapshots.")
    else:
        reasons.append(
            "Only one disposition snapshot so far; trend will sharpen as the archive grows."
        )

    return reasons


def rank_forecasts(
    weapons: list[dict],
    *,
    config: ForecastConfig = DEFAULT_CONFIG,
    direction: str | None = None,
) -> list[DispositionForecast]:
    """Forecast a batch and sort by conviction (confidence, then |pressure|).

    Each ``weapons`` row: ``{slug, name, disposition, history?, n_auctions?, median_price?}``.
    Rows without a usable current disposition are skipped. Pass ``direction`` to keep only
    "buff" or "nerf" calls.
    """
    out: list[DispositionForecast] = []
    for w in weapons:
        disp = w.get("disposition")
        if disp is None:
            continue
        out.append(
            forecast_disposition(
                slug=w["slug"],
                name=w.get("name"),
                current_disposition=disp,
                history=w.get("history"),
                n_auctions=w.get("n_auctions"),
                median_price=w.get("median_price"),
                config=config,
            )
        )
    if direction:
        out = [f for f in out if f.direction == direction]
    return sorted(out, key=lambda f: (f.confidence, abs(f.pressure)), reverse=True)


def with_reasons(forecast: DispositionForecast, extra: list[str]) -> DispositionForecast:
    """Return a copy with additional rationale appended (helper for callers/tests)."""
    return replace(forecast, reasons=[*forecast.reasons, *extra])


def to_dict(forecast: DispositionForecast) -> dict[str, Any]:
    """Plain dict for JSON responses (FastAPI also handles dataclasses, but explicit is safer)."""
    return {
        "slug": forecast.slug,
        "name": forecast.name,
        "current_disposition": forecast.current_disposition,
        "direction": forecast.direction,
        "pressure": forecast.pressure,
        "confidence": forecast.confidence,
        "reasons": forecast.reasons,
        "n_history": forecast.n_history,
        "demand": forecast.demand,
    }
