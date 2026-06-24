from __future__ import annotations

from voidbroker.backtest import backtest_disposition, report_to_dict


def _hist(*vals):
    return [{"captured_at": f"t{i}", "disposition": v} for i, v in enumerate(vals)]


def test_no_changes_yields_empty_report():
    weapons = [{"slug": "x", "name": "X", "history": _hist(1.0, 1.0, 1.0)}]
    r = backtest_disposition(weapons)
    assert r.total_changes == 0
    assert r.called == 0
    assert r.hit_rate is None
    assert r.base_rate is None


def test_scores_a_correct_nerf_call():
    # High disposition that then falls: reversion predicts nerf, realized is nerf -> correct.
    weapons = [{"slug": "kuva_bramma", "name": "Kuva Bramma", "history": _hist(1.5, 1.3)}]
    r = backtest_disposition(weapons)
    assert r.total_changes == 1
    case = r.cases[0]
    assert case.realized == "nerf"
    assert case.predicted == "nerf"
    assert case.correct is True
    assert r.hit_rate == 1.0


def test_low_disposition_rise_is_correct_buff():
    weapons = [{"slug": "latron", "name": "Latron", "history": _hist(0.6, 0.8)}]
    r = backtest_disposition(weapons)
    assert r.cases[0].realized == "buff"
    assert r.cases[0].predicted == "buff"
    assert r.cases[0].correct is True


def test_scores_every_consecutive_change():
    # Two moves in one series are two scored cases (walk-forward, not just the last).
    weapons = [{"slug": "x", "history": _hist(1.5, 1.55, 1.3)}]
    r = backtest_disposition(weapons)
    assert r.total_changes == 2
    assert [c.realized for c in r.cases] == ["buff", "nerf"]


def test_base_rate_and_hit_rate_aggregate():
    weapons = [
        {"slug": "a", "history": _hist(1.5, 1.3)},   # nerf, model: nerf (correct)
        {"slug": "b", "history": _hist(1.5, 1.2)},   # nerf, model: nerf (correct)
        {"slug": "c", "history": _hist(0.6, 0.9)},   # buff, model: buff (correct)
    ]
    r = backtest_disposition(weapons)
    assert r.total_changes == 3
    # 2 nerfs, 1 buff -> majority baseline = 2/3.
    assert r.buff_share == round(1 / 3, 3)
    assert r.base_rate == round(2 / 3, 3)
    assert 0.0 <= (r.hit_rate or 0) <= 1.0


def test_calibration_buckets_present():
    weapons = [{"slug": "a", "history": _hist(1.5, 1.3, 1.5, 1.2)}]
    r = backtest_disposition(weapons)
    assert len(r.calibration) == 4
    assert all("bucket" in b and "n" in b for b in r.calibration)
    # Buckets sum to the number of directional calls.
    assert sum(b["n"] for b in r.calibration) == r.called


def test_report_to_dict_caps_cases():
    weapons = [{"slug": "a", "history": _hist(1.5, 1.3, 1.5, 1.2, 1.5)}]
    r = backtest_disposition(weapons)
    d = report_to_dict(r, include_cases=1)
    assert len(d["cases"]) == 1
    assert set(d) == {
        "total_changes", "called", "correct", "hit_rate",
        "base_rate", "buff_share", "calibration", "cases",
    }
