from __future__ import annotations

from voidbroker.models import (
    Item,
    Order,
    RivenAttribute,
    RivenAuction,
    RivenWeapon,
    StatRecord,
)


def test_item_from_api_flattens_i18n(sample_item_raw):
    item = Item.from_api(sample_item_raw, language="en")
    assert item.slug == "secura_dual_cestra"
    assert item.name == "Secura Dual Cestra"
    assert item.is_riven is False


def test_item_i18n_falls_back_to_english_then_any(sample_item_raw):
    # Requested language missing -> falls back to English.
    item = Item.from_api(sample_item_raw, language="ru")
    assert item.name == "Secura Dual Cestra"


def test_item_is_riven_by_tag(sample_riven_item_raw):
    item = Item.from_api(sample_riven_item_raw, language="en")
    assert item.is_riven is True


def test_riven_weapon_from_api(sample_weapon_raw):
    w = RivenWeapon.from_api(sample_weapon_raw, language="en")
    assert w.slug == "kulstar"
    assert w.disposition == 1.3
    assert w.riven_type == "pistol"
    assert w.req_mastery_rank == 5
    assert w.name == "Kulstar"


def test_stat_record_parses(sample_stat_rows):
    rec = StatRecord.model_validate(sample_stat_rows[0])
    assert rec.volume == 137
    assert rec.median == 88
    assert rec.datetime.year == 2026


def test_order_alias_parsing_and_liveness(sample_orders_raw):
    live = Order.model_validate(sample_orders_raw[0])
    assert live.per_trade == 1
    assert live.user.ingame_name == "p1"
    assert live.is_live is True

    offline = Order.model_validate(sample_orders_raw[2])
    assert offline.is_live is False


def test_riven_attribute_from_api(sample_riven_attr_raw):
    attr = RivenAttribute.from_api(sample_riven_attr_raw, "en")
    assert attr.slug == "punch_through"
    assert attr.prefix == "Lexi"
    assert attr.suffix == "Nok"
    assert attr.name == "Punch Through"


def test_riven_auction_from_api_flattens_item_and_owner(sample_auction_raw):
    a = RivenAuction.from_api(sample_auction_raw)
    assert a.weapon_url_name == "kulstar"
    assert a.buyout_price == 40
    assert a.owner_status == "ingame"
    assert a.is_live is True
    assert len(a.attributes) == 2
    pos = [s for s in a.attributes if s.positive]
    assert pos[0].url_name == "zoom"


def test_riven_auction_not_live_when_closed(sample_auction_raw):
    raw = {**sample_auction_raw, "closed": True}
    assert RivenAuction.from_api(raw).is_live is False
