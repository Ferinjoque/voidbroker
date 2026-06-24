from __future__ import annotations

from voidbroker.models import RivenAuction
from voidbroker.rivens import (
    appraise,
    attribute_signature,
    effective_price,
    find_undervalued,
    roll_quality,
)


def make_val_auction(aid, price, stat, value, status="ingame"):
    return RivenAuction(
        id=aid,
        weapon_url_name="kulstar",
        buyout_price=price,
        starting_price=price,
        is_direct_sell=True,
        visible=True,
        closed=False,
        owner_status=status,
        attributes=[{"url_name": stat, "value": value, "positive": True}],
    )


def make_auction(aid, price, pos, neg, status="ingame", direct=True):
    return RivenAuction(
        id=aid,
        weapon_url_name="kulstar",
        buyout_price=price,
        starting_price=price,
        is_direct_sell=direct,
        visible=True,
        closed=False,
        owner_status=status,
        attributes=[{"url_name": p, "value": 100, "positive": True} for p in pos]
        + [{"url_name": n, "value": -10, "positive": False} for n in neg],
    )


def test_attribute_signature_is_canonical():
    a = make_auction("1", 50, ["multishot", "crit_damage"], ["zoom"])
    b = make_auction("2", 50, ["crit_damage", "multishot"], ["zoom"])  # reordered
    assert attribute_signature(a) == attribute_signature(b)
    assert attribute_signature(a) == "+crit_damage,multishot|-zoom"


def test_effective_price_prefers_buyout_for_direct_sell():
    a = make_auction("1", 80, ["multishot"], [], direct=True)
    assert effective_price(a) == 80


def test_appraise_groups_by_signature_and_ignores_offline():
    auctions = [
        make_auction("1", 100, ["multishot"], []),
        make_auction("2", 120, ["multishot"], []),
        make_auction("3", 5, ["multishot"], [], status="offline"),  # excluded
        make_auction("4", 300, ["crit_damage"], []),                # different group
    ]
    comps = appraise(auctions)
    assert comps["+multishot|-"].count == 2
    assert comps["+multishot|-"].median_price == 110
    assert comps["+crit_damage|-"].count == 1


def test_find_undervalued_flags_cheap_listing_in_deep_group():
    # 5 comparable listings around 100, plus one priced at 40 (60% off).
    auctions = [make_auction(str(i), 100, ["multishot"], []) for i in range(5)]
    auctions.append(make_auction("deal", 40, ["multishot"], []))

    deals = find_undervalued("kulstar", auctions, min_comparables=4, min_discount=0.25)
    assert len(deals) == 1
    assert deals[0].auction_id == "deal"
    assert deals[0].discount_pct >= 0.5


def test_positives_only_signature_collapses_negatives():
    a = make_auction("1", 50, ["multishot"], ["zoom"])
    b = make_auction("2", 50, ["multishot"], ["recoil"])  # different negative
    # Strict: different groups. positives_only: same group.
    assert attribute_signature(a) != attribute_signature(b)
    sig_a = attribute_signature(a, positives_only=True)
    sig_b = attribute_signature(b, positives_only=True)
    assert sig_a == sig_b


def test_positives_only_deepens_comparable_groups():
    # Same positive, three different negatives -> one positives_only group of 4 (+a deal).
    auctions = [
        make_auction("1", 100, ["multishot"], ["zoom"]),
        make_auction("2", 100, ["multishot"], ["recoil"]),
        make_auction("3", 100, ["multishot"], ["impact_damage"]),
        make_auction("4", 100, ["multishot"], []),
        make_auction("deal", 40, ["multishot"], ["zoom"]),
    ]
    strict = find_undervalued("kulstar", auctions, min_comparables=4, min_discount=0.25)
    loose = find_undervalued(
        "kulstar", auctions, min_comparables=4, min_discount=0.25, positives_only=True
    )
    assert strict == []  # exact-signature groups too thin
    assert len(loose) == 1 and loose[0].auction_id == "deal"


def test_find_undervalued_requires_minimum_comparables():
    # Only 2 listings — too thin to trust even though one is "cheap".
    auctions = [
        make_auction("1", 100, ["multishot"], []),
        make_auction("deal", 40, ["multishot"], []),
    ]
    assert find_undervalued("kulstar", auctions, min_comparables=4) == []


def test_roll_quality_ranks_high_values_above_low():
    vals = [60, 70, 80, 90, 100]
    group = [make_val_auction(str(i), 100, "multishot", v) for i, v in enumerate(vals)]
    strong = group[-1]  # value 100
    weak = group[0]      # value 60
    assert roll_quality(strong, group) > roll_quality(weak, group)


def test_strong_roll_deal_outranks_weak_roll_deal():
    # Same discount, different roll: the god-roll must rank above the weak roll, and the
    # weak roll's score is discounted for being cheap-for-a-reason.
    group = [make_val_auction(str(i), 100, "multishot", v) for i, v in enumerate([70, 80, 80, 90])]
    group.append(make_val_auction("strong", 40, "multishot", 100))
    group.append(make_val_auction("weak", 40, "multishot", 50))

    deals = find_undervalued("kulstar", group, min_comparables=4, min_discount=0.25)
    ids = [d.auction_id for d in deals]
    assert ids.index("strong") < ids.index("weak")

    strong = next(d for d in deals if d.auction_id == "strong")
    weak = next(d for d in deals if d.auction_id == "weak")
    assert strong.discount_pct == weak.discount_pct  # same price vs median
    assert strong.roll_quality > weak.roll_quality
    assert strong.score > weak.score
    assert strong.roll_label in ("strong", "above avg")
