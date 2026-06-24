from __future__ import annotations

from voidbroker.signals import (
    detect_disposition_changes,
    estimate_flip_days,
    liquidity_factor,
    rank_opportunities,
    score_opportunity,
)


def test_liquidity_factor_bounds():
    assert liquidity_factor(None) == 0.0
    assert liquidity_factor(0) == 0.0
    assert 0 < liquidity_factor(10) < liquidity_factor(100) < 1.0


def test_estimate_flip_days_inverse_to_volume():
    assert estimate_flip_days(5, 0) == 60.0  # no trades -> clamp to max
    fast = estimate_flip_days(2, 100)
    slow = estimate_flip_days(2, 5)
    assert fast < slow


def test_score_opportunity_prefers_moving_avg_baseline():
    row = {
        "slug": "x", "sell_min": 80,
        "baseline_moving_avg": 100, "baseline_median": 90,
        "recent_volume": 50, "n_sell_live": 3,
    }
    opp = score_opportunity(row)
    assert opp is not None
    assert opp.baseline == 100  # moving_avg wins over median
    assert opp.margin == 20
    assert opp.margin_pct == 0.20
    assert opp.score > 0


def test_score_opportunity_rejects_thin_margin_and_missing_data():
    thin = {"slug": "x", "sell_min": 98, "baseline_moving_avg": 100, "recent_volume": 50}
    assert score_opportunity(thin) is None  # 2% < 5% threshold

    no_baseline = {"slug": "y", "sell_min": 50, "recent_volume": 10}
    assert score_opportunity(no_baseline) is None


def test_rank_opportunities_sorts_and_filters():
    rows = [
        {"slug": "lowliq", "sell_min": 50, "baseline_moving_avg": 100, "recent_volume": 1,
         "n_sell_live": 1},
        {"slug": "highliq", "sell_min": 50, "baseline_moving_avg": 100, "recent_volume": 100,
         "n_sell_live": 1},
        {"slug": "thin", "sell_min": 99, "baseline_moving_avg": 100, "recent_volume": 100},
    ]
    ranked = rank_opportunities(rows)
    # Same margin, but the liquid item must outrank the illiquid one; thin is filtered out.
    assert [o.slug for o in ranked] == ["highliq", "lowliq"]


def test_detect_disposition_changes_classifies_buff_and_nerf():
    history = [
        {"captured_at": "t1", "disposition": 1.3},
        {"captured_at": "t2", "disposition": 1.3},  # no change
        {"captured_at": "t3", "disposition": 1.1},  # nerf
        {"captured_at": "t4", "disposition": 1.2},  # buff
    ]
    changes = detect_disposition_changes("kulstar", history)
    assert len(changes) == 2
    assert changes[0].direction == "nerf"
    assert changes[0].delta == -0.2
    assert changes[1].direction == "buff"
    assert changes[1].at == "t4"


def test_detect_disposition_changes_stable_history():
    history = [{"captured_at": "t1", "disposition": 1.0}, {"captured_at": "t2", "disposition": 1.0}]
    assert detect_disposition_changes("x", history) == []
