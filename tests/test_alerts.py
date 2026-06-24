from __future__ import annotations

from voidbroker.alerts import AlertThresholds, render_markdown, select_alerts


def test_selects_only_high_conviction():
    digest = {
        "opportunities": [
            {"slug": "deep", "name": "Deep", "sell_min": 30, "margin_pct": 0.40,
             "flip_days_est": 1},
            {"slug": "shallow", "name": "Shallow", "sell_min": 30, "margin_pct": 0.10},
        ],
        "riven_deals": [
            {"weapon_slug": "kuva_bramma", "weapon_name": "Kuva Bramma", "signature": "+x",
             "price": 200, "comparable_median": 500, "discount_pct": 0.6, "roll_label": "strong"},
            {"weapon_slug": "w2", "signature": "+y", "price": 9, "comparable_median": 10,
             "discount_pct": 0.5, "roll_label": "weak"},  # weak roll -> skipped
        ],
        "disposition_forecasts": [
            {"slug": "stug", "name": "Stug", "direction": "nerf", "current_disposition": 1.5,
             "confidence": 0.7},
            {"slug": "low", "name": "Low", "direction": "nerf", "current_disposition": 1.4,
             "confidence": 0.3},  # low conf -> skipped
        ],
        "resurgence": {"best_buys": [
            {"slug": "equinox_prime_set", "item": "Equinox Prime", "price_now": 50,
             "change_since_resurgence": -0.30},
        ]},
        "void_trader": None,
    }
    arbitrage = [
        {"slug": "kogake_prime_set", "name": "Kogake Prime Set", "direction": "build",
         "set_price": 98, "parts_cost": 43, "profit": 55, "margin_pct": 1.28},
    ]
    alerts = select_alerts(digest, arbitrage)
    kinds = {a.kind for a in alerts}
    assert kinds == {"opportunity", "riven", "nerf", "resurgence", "arbitrage"}
    keys = {a.key for a in alerts}
    assert "opp:deep" in keys and "opp:shallow" not in keys
    assert any(k.startswith("riven:kuva_bramma") for k in keys)
    assert "nerf:stug" in keys and "nerf:low" not in keys
    assert "arb:kogake_prime_set" in keys


def test_thresholds_respected():
    digest = {"opportunities": [{"slug": "x", "name": "X", "sell_min": 1, "margin_pct": 0.2}]}
    assert select_alerts(digest, t=AlertThresholds(opp_margin=0.30)) == []
    assert len(select_alerts(digest, t=AlertThresholds(opp_margin=0.15))) == 1


def test_render_markdown_marks_new():
    digest = {"opportunities": [{"slug": "x", "name": "X", "sell_min": 5, "margin_pct": 0.5,
                                 "flip_days_est": 1}]}
    alerts = select_alerts(digest)
    md = render_markdown(alerts, "2026-06-23", new_keys={"opp:x"})
    assert "voidbroker alerts" in md and "★" in md and "Buy X" in md
    assert "_No high-conviction" in render_markdown([], "2026-06-23")
