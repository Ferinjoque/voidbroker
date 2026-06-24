"""Walk-forward backtest of the disposition predictor, pure functions, no I/O.

The predictor is only worth trusting if its past calls would have been right. This replays
the archive: for every realized disposition change, it recomputes the forecast using *only*
the snapshots recorded before that change, then scores whether the predicted direction
matched what DE actually did.

It scores the **price-independent core** of the model (mean-reversion + momentum) and
deliberately omits the demand proxy: historical riven-demand *as of* a past change is
generally not in a shallow archive, and faking it would make the harness lie. Demand
calibration becomes possible once auction history is deep (see ROADMAP B2/B3). What this
measures is exactly the part that should anticipate DE's mean-reverting rebalances.

Read the headline as: of the directional calls the model would have made, what fraction
were right, versus the naive base rate of always guessing the majority direction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

from .predict import DEFAULT_CONFIG, ForecastConfig, forecast_disposition

# Confidence buckets for the calibration table (lower-inclusive bounds, as percents).
_CALIB_BINS = [(0, 25), (25, 50), (50, 75), (75, 101)]


@dataclass(frozen=True)
class BacktestCase:
    slug: str
    name: str | None
    at: object               # captured_at of the realized change
    from_disposition: float
    to_disposition: float
    realized: str            # "buff" | "nerf"
    predicted: str           # forecast.direction from pre-change data
    pressure: float
    confidence: float
    called: bool             # the model made a directional (non-stable) call
    correct: bool            # called and matched the realized direction


@dataclass(frozen=True)
class BacktestReport:
    total_changes: int
    called: int              # directional predictions (non-stable)
    correct: int
    hit_rate: float | None   # correct / called
    base_rate: float | None  # naive baseline: share of the *majority* realized direction
    buff_share: float | None # share of changes that were buffs (context for base_rate)
    calibration: list[dict] = field(default_factory=list)
    cases: list[BacktestCase] = field(default_factory=list)


def _weapon_cases(
    slug: str, name: str | None, history: list[dict], config: ForecastConfig
) -> list[BacktestCase]:
    """Score every realized change in one weapon's ascending disposition history."""
    series = [r for r in history if r.get("disposition") is not None]
    cases: list[BacktestCase] = []
    for i in range(1, len(series)):
        prev = series[i - 1]["disposition"]
        cur = series[i]["disposition"]
        if cur == prev:
            continue  # no change to predict
        # Everything up to and including `prev` is the evidence available before the move.
        f = forecast_disposition(slug, name, prev, history=series[:i], config=config)
        realized = "buff" if cur > prev else "nerf"
        called = f.direction in ("buff", "nerf")
        cases.append(
            BacktestCase(
                slug=slug,
                name=name,
                at=series[i].get("captured_at"),
                from_disposition=round(prev, 3),
                to_disposition=round(cur, 3),
                realized=realized,
                predicted=f.direction,
                pressure=f.pressure,
                confidence=f.confidence,
                called=called,
                correct=called and f.direction == realized,
            )
        )
    return cases


def _calibration(cases: list[BacktestCase]) -> list[dict]:
    """Hit-rate per confidence bucket among directional calls (is 70% really ~70%?)."""
    called = [c for c in cases if c.called]
    out: list[dict] = []
    for lo, hi in _CALIB_BINS:
        bucket = [c for c in called if lo <= c.confidence * 100 < hi]
        n = len(bucket)
        hits = sum(1 for c in bucket if c.correct)
        out.append(
            {
                "bucket": f"{lo}-{min(hi, 100)}%",
                "n": n,
                "hit_rate": round(hits / n, 3) if n else None,
            }
        )
    return out


def backtest_disposition(
    weapons: list[dict], *, config: ForecastConfig = DEFAULT_CONFIG
) -> BacktestReport:
    """Replay every weapon's history and score the predictor's would-have-been calls.

    Each ``weapons`` row: ``{slug, name?, history}`` where history is ascending
    ``{captured_at, disposition}`` rows. Returns aggregate accuracy, the naive base rate to
    beat, a calibration table, and the per-change cases.
    """
    cases: list[BacktestCase] = []
    for w in weapons:
        cases.extend(
            _weapon_cases(w["slug"], w.get("name"), w.get("history") or [], config)
        )

    total = len(cases)
    called_cases = [c for c in cases if c.called]
    called = len(called_cases)
    correct = sum(1 for c in called_cases if c.correct)

    n_buff = sum(1 for c in cases if c.realized == "buff")
    buff_share = round(n_buff / total, 3) if total else None
    # Base rate to beat: always guess the more common realized direction.
    base_rate = round(max(n_buff, total - n_buff) / total, 3) if total else None

    return BacktestReport(
        total_changes=total,
        called=called,
        correct=correct,
        hit_rate=round(correct / called, 3) if called else None,
        base_rate=base_rate,
        buff_share=buff_share,
        calibration=_calibration(cases),
        cases=cases,
    )


@dataclass(frozen=True)
class ReversionReport:
    """Does buying an item when its close dips below its moving-average baseline pay off?

    Returns are reported as **medians**, not means: plat prices are fat-tailed (a 1p item
    spiking to 50p is +4900%), so the mean is dominated by a handful of cheap outliers and is
    meaningless. The median return and the hit rate are the trustworthy figures.
    """

    horizon_days: int
    dip_pct: float
    observations: int          # all (day, day+horizon) pairs considered
    base_median_return: float | None   # buying on any day, held `horizon`
    signals: int               # dip-below-baseline entries
    signal_median_return: float | None
    signal_hit_rate: float | None      # share of dip entries that were up at exit
    median_gap_closed: float | None    # median fraction of the dip-to-baseline gap recovered
    edge: float | None         # signal_median_return - base_median_return


def backtest_reversion(
    items: list[dict], *, dip_pct: float = 0.08, horizon: int = 7
) -> ReversionReport:
    """Backtest the opportunity thesis on archived daily closes.

    Each ``items`` row: ``{slug, closes: [float], mas: [float|None]}`` (ascending). For every
    day, the forward ``horizon``-day return is recorded as the baseline. Days whose close sits
    at least ``dip_pct`` below the moving-average baseline are the *signal* entries. If the
    signal's median forward return beats the baseline (positive ``edge``), buying the dip has
    historically paid, the empirical basis for the opportunity score's mean-reversion bet.
    """
    base: list[float] = []
    sig: list[float] = []
    gaps: list[float] = []

    for it in items:
        closes = it.get("closes") or []
        mas = it.get("mas") or []
        n = len(closes)
        for i in range(n - horizon):
            entry = closes[i]
            exit_ = closes[i + horizon]
            if not entry or entry <= 0:
                continue
            ret = (exit_ - entry) / entry
            base.append(ret)
            ma = mas[i] if i < len(mas) else None
            if ma and entry <= ma * (1.0 - dip_pct):
                sig.append(ret)
                if ma > entry:
                    gaps.append((exit_ - entry) / (ma - entry))

    base_med = round(median(base), 4) if base else None
    sig_med = round(median(sig), 4) if sig else None
    hit = round(sum(1 for r in sig if r > 0) / len(sig), 3) if sig else None
    edge = (
        round(sig_med - base_med, 4)
        if (sig_med is not None and base_med is not None)
        else None
    )

    return ReversionReport(
        horizon_days=horizon,
        dip_pct=dip_pct,
        observations=len(base),
        base_median_return=base_med,
        signals=len(sig),
        signal_median_return=sig_med,
        signal_hit_rate=hit,
        median_gap_closed=round(median(gaps), 3) if gaps else None,
        edge=edge,
    )


def report_to_dict(report: BacktestReport, *, include_cases: int | None = None) -> dict:
    """JSON-friendly view. ``include_cases`` caps how many per-change cases are returned."""
    cases = report.cases if include_cases is None else report.cases[:include_cases]
    return {
        "total_changes": report.total_changes,
        "called": report.called,
        "correct": report.correct,
        "hit_rate": report.hit_rate,
        "base_rate": report.base_rate,
        "buff_share": report.buff_share,
        "calibration": report.calibration,
        "cases": [
            {
                "slug": c.slug,
                "name": c.name,
                "at": c.at,
                "from_disposition": c.from_disposition,
                "to_disposition": c.to_disposition,
                "realized": c.realized,
                "predicted": c.predicted,
                "pressure": c.pressure,
                "confidence": c.confidence,
                "correct": c.correct,
            }
            for c in cases
        ],
    }
