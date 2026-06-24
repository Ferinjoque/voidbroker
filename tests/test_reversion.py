from __future__ import annotations

from voidbroker.backtest import backtest_reversion


def test_no_signals_when_never_dips():
    # Price always at/above the moving average -> no dip entries.
    item = {"slug": "x", "closes": [100] * 30, "mas": [100] * 30}
    r = backtest_reversion([item], dip_pct=0.08, horizon=7)
    assert r.signals == 0
    assert r.observations > 0
    assert r.signal_median_return is None


def test_reverting_dips_show_positive_edge():
    # Construct a series that dips ~15% below baseline then recovers within the horizon.
    closes, mas = [], []
    for _ in range(6):
        # baseline 100, a dip to 85, then back to ~100 a week later
        closes += [100, 100, 85, 90, 95, 100, 100]
        mas += [100] * 7
    r = backtest_reversion([{"slug": "x", "closes": closes, "mas": mas}], dip_pct=0.08, horizon=4)
    assert r.signals > 0
    assert r.signal_median_return is not None and r.signal_median_return > 0
    assert r.signal_hit_rate is not None and r.signal_hit_rate > 0.5
    # Buying the dip beat buying any day.
    assert r.edge is not None and r.edge > 0


def test_gap_closed_tracked():
    closes = [100, 80, 90, 100, 100, 100]  # dip to 80 (20% below ma 100), recovers
    mas = [100] * 6
    r = backtest_reversion([{"slug": "x", "closes": closes, "mas": mas}], dip_pct=0.1, horizon=2)
    assert r.signals >= 1
    assert r.median_gap_closed is not None  # (90-80)/(100-80) = 0.5 for the first signal


def test_handles_missing_ma_and_zero_prices():
    item = {"slug": "x", "closes": [0, 100, 90, 100, 100], "mas": [None, None, 100, 100, 100]}
    r = backtest_reversion([item], dip_pct=0.05, horizon=1)
    # No crash; entries with no MA or zero price are skipped from the signal set.
    assert r.observations >= 1
