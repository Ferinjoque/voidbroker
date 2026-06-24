from __future__ import annotations

from voidbroker.arbitrage import rank_ducat_efficiency, set_arbitrage


def test_build_flip_when_parts_cheaper_than_set():
    sets = [{
        "slug": "x_prime_set", "name": "X Prime Set", "set_price": 100,
        "parts": [
            {"slug": "a", "price": 20}, {"slug": "b", "price": 30}, {"slug": "c", "price": 20},
        ],
    }]  # parts cost 70 vs set 100 -> build, profit 30, margin 30/70
    deals = set_arbitrage(sets, min_margin=0.10)
    assert len(deals) == 1
    d = deals[0]
    assert d.direction == "build"
    assert d.parts_cost == 70 and d.set_price == 100
    assert d.profit == 30
    assert round(d.margin_pct, 2) == round(30 / 70, 2)


def test_split_flip_when_set_cheaper_than_parts():
    sets = [{
        "slug": "y_prime_set", "name": "Y", "set_price": 50,
        "parts": [{"slug": "a", "price": 40}, {"slug": "b", "price": 40}],
    }]  # parts 80 vs set 50 -> split, profit 30, margin 30/50
    deals = set_arbitrage(sets, min_margin=0.10)
    assert deals[0].direction == "split"
    assert deals[0].profit == 30
    assert deals[0].margin_pct == 0.6


def test_skips_incomplete_pricing_and_thin_margin():
    incomplete = {"slug": "s", "set_price": 100,
                  "parts": [{"slug": "a", "price": 20}, {"slug": "b", "price": None}]}
    thin = {"slug": "t", "set_price": 102,
            "parts": [{"slug": "a", "price": 50}, {"slug": "b", "price": 50}]}  # 2% margin
    assert set_arbitrage([incomplete], min_margin=0.10) == []
    assert set_arbitrage([thin], min_margin=0.10) == []


def test_discards_implausible_margin_as_bad_data():
    # A "set" priced absurdly high vs its parts (stale/illiquid price) is dropped, not surfaced.
    sets = [{"slug": "junk", "set_price": 50000,
             "parts": [{"slug": "a", "price": 50}, {"slug": "b", "price": 50}]}]
    assert set_arbitrage(sets, min_margin=0.10, max_margin=1.5) == []


def test_requires_minimum_parts():
    one_part = {"slug": "s", "set_price": 100, "parts": [{"slug": "a", "price": 10}]}
    assert set_arbitrage([one_part], min_parts=2) == []


def test_ducat_efficiency_ranks_and_filters():
    items = [
        {"slug": "cheap_high", "name": "A", "thumb": None, "ducats": 45, "price": 5},  # 9.0
        {"slug": "pricey", "name": "B", "thumb": None, "ducats": 45, "price": 15},  # 3.0
        {"slug": "low_ducat", "name": "C", "thumb": None, "ducats": 10, "price": 2},  # ducats<15
        {"slug": "noise", "name": "D", "thumb": None, "ducats": 45, "price": 0.5},  # price<1
    ]
    ranked = rank_ducat_efficiency(items, min_ducats=15, min_price=1.0)
    assert [d.slug for d in ranked] == ["cheap_high", "pricey"]
    assert ranked[0].ducats_per_plat == 9.0
