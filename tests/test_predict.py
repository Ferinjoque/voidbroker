from __future__ import annotations

from voidbroker.predict import (
    DEFAULT_CONFIG,
    demand_norm,
    demand_pressure,
    forecast_disposition,
    momentum_pressure,
    rank_forecasts,
    reversion_pressure,
    to_dict,
)


def test_reversion_pressure_signs_and_bounds():
    # Below nominal -> buff pressure (+); above -> nerf pressure (-); within [-1, 1].
    assert reversion_pressure(0.5) > 0
    assert reversion_pressure(1.55) < 0
    assert abs(reversion_pressure(1.0)) < 1e-9
    assert -1.0 <= reversion_pressure(2.0) <= 1.0
    assert -1.0 <= reversion_pressure(0.0) <= 1.0


def test_demand_norm_saturates_and_handles_unknown():
    assert demand_norm(None, None) is None
    assert demand_norm(0, 0) is None
    low = demand_norm(1, 50)
    high = demand_norm(40, 1200)
    assert low is not None and high is not None
    assert 0.0 <= low < high <= 1.0


def test_demand_pressure_inverts_demand():
    # Strong demand -> nerf (negative); thin demand -> buff (positive).
    assert demand_pressure(0.9) < 0
    assert demand_pressure(0.1) > 0
    assert demand_pressure(None) is None


def test_momentum_needs_two_points():
    assert momentum_pressure([]) is None
    assert momentum_pressure([{"disposition": 1.0}]) is None
    up = momentum_pressure([{"disposition": 1.0}, {"disposition": 1.2}])
    down = momentum_pressure([{"disposition": 1.2}, {"disposition": 1.0}])
    assert up is not None and up > 0
    assert down is not None and down < 0


def test_forecast_high_disposition_strong_demand_is_nerf():
    f = forecast_disposition(
        slug="kuva_bramma",
        name="Kuva Bramma",
        current_disposition=1.45,
        history=[
            {"captured_at": "t1", "disposition": 1.5},
            {"captured_at": "t2", "disposition": 1.45},
        ],
        n_auctions=40,
        median_price=1200,
    )
    assert f.direction == "nerf"
    assert f.pressure < 0
    assert f.confidence > 0
    # Full evidence (all three components) should out-confide a reversion-only call.
    assert f.demand is not None and f.n_history == 2


def test_forecast_low_disposition_thin_demand_is_buff():
    f = forecast_disposition(
        slug="latron",
        name="Latron",
        current_disposition=0.6,
        history=[
            {"captured_at": "t1", "disposition": 0.55},
            {"captured_at": "t2", "disposition": 0.6},
        ],
        n_auctions=1,
        median_price=40,
    )
    assert f.direction == "buff"
    assert f.pressure > 0


def test_forecast_degrades_without_demand_or_history():
    full = forecast_disposition(
        "x", "X", 1.5, history=[{"disposition": 1.5}, {"disposition": 1.5}],
        n_auctions=30, median_price=900,
    )
    sparse = forecast_disposition("x", "X", 1.5)
    # Same lean (nerf), but sparse evidence must be less confident than full evidence.
    assert sparse.direction == full.direction == "nerf"
    assert sparse.confidence < full.confidence
    assert sparse.demand is None and sparse.n_history == 0


def test_forecast_near_nominal_is_stable():
    f = forecast_disposition("x", "X", 1.0)
    assert f.direction == "stable"
    assert abs(f.pressure) <= DEFAULT_CONFIG.direction_threshold


def test_forecast_always_has_reasons():
    f = forecast_disposition("x", "X", 1.4, n_auctions=20, median_price=600)
    assert f.reasons
    assert all(isinstance(r, str) and r for r in f.reasons)


def test_rank_forecasts_sorts_by_conviction_and_filters_direction():
    weapons = [
        {"slug": "stable", "name": "Stable", "disposition": 1.0},
        {"slug": "strongnerf", "name": "Nerf", "disposition": 1.5,
         "n_auctions": 50, "median_price": 1500,
         "history": [{"disposition": 1.5}, {"disposition": 1.5}]},
        {"slug": "weakbuff", "name": "Buff", "disposition": 0.7},
        {"slug": "nodisp", "name": "Skip"},  # no disposition -> skipped
    ]
    ranked = rank_forecasts(weapons)
    slugs = [f.slug for f in ranked]
    assert "nodisp" not in slugs
    assert ranked[0].slug == "strongnerf"  # highest conviction first

    nerfs = rank_forecasts(weapons, direction="nerf")
    assert all(f.direction == "nerf" for f in nerfs)
    assert "strongnerf" in [f.slug for f in nerfs]


def test_to_dict_round_trips_fields():
    f = forecast_disposition("x", "X", 1.4, n_auctions=10, median_price=300)
    d = to_dict(f)
    assert d["slug"] == "x"
    assert d["direction"] == f.direction
    assert d["pressure"] == f.pressure
    assert set(d) == {
        "slug", "name", "current_disposition", "direction", "pressure",
        "confidence", "reasons", "n_history", "demand",
    }
