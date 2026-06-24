from __future__ import annotations

from datetime import UTC, datetime

from voidbroker.digest import build_digest


def test_digest_shape_on_empty_archive(storage):
    d = build_digest(storage, datetime(2026, 6, 23, tzinfo=UTC))
    assert set(d) == {
        "opportunities", "riven_deals", "disposition_forecasts", "resurgence", "void_trader",
    }
    assert d["opportunities"] == []
    assert d["riven_deals"] == []
    assert d["disposition_forecasts"] == []
    assert d["resurgence"] is None
    assert d["void_trader"] is None


def test_digest_includes_resurgence_when_present(storage, sample_resurgence_raw):
    from voidbroker.worldstate import ResurgenceState

    storage.record_resurgence(ResurgenceState.from_api(sample_resurgence_raw))
    d = build_digest(storage, datetime(2026, 6, 20, tzinfo=UTC))
    assert d["resurgence"] is not None
    assert d["resurgence"]["status"]["phase"] == "active"
    assert "best_buys" in d["resurgence"]
