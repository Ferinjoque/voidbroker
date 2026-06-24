"""Shared fixtures — canned API payloads (real shapes) and an in-memory archive."""

from __future__ import annotations

import pytest

from voidbroker.storage import Storage


@pytest.fixture
def sample_item_raw() -> dict:
    return {
        "id": "54aae292e7798909064f1575",
        "slug": "secura_dual_cestra",
        "gameRef": "/Lotus/Weapons/Syndicates/PerrinSequence/Pistols/PSDualCestra",
        "tags": ["syndicate", "weapon", "secondary"],
        "i18n": {"en": {"name": "Secura Dual Cestra", "icon": "x.png", "thumb": "t.png"}},
    }


@pytest.fixture
def sample_riven_item_raw() -> dict:
    return {
        "id": "abc123",
        "slug": "bramma_riven_mod",
        "tags": ["riven", "mod"],
        "i18n": {"en": {"name": "Bramma Riven Mod"}},
    }


@pytest.fixture
def sample_weapon_raw() -> dict:
    return {
        "id": "5c5ca81696e8d2003834fdcc",
        "slug": "kulstar",
        "gameRef": "/Lotus/Weapons/Grineer/Pistols/GrnTorpedoPistol/GrnTorpedoPistol",
        "group": "secondary",
        "rivenType": "pistol",
        "disposition": 1.3,
        "reqMasteryRank": 5,
        "i18n": {"en": {"name": "Kulstar"}},
    }


@pytest.fixture
def sample_stat_rows() -> list[dict]:
    return [
        {
            "datetime": "2026-06-20T00:00:00.000+00:00",
            "volume": 137, "min_price": 79, "max_price": 95, "open_price": 95,
            "closed_price": 80, "avg_price": 87, "wa_price": 86.555, "median": 88,
            "moving_avg": 87, "donch_top": 95, "donch_bot": 79, "id": "x1",
        },
        {
            "datetime": "2026-06-21T00:00:00.000+00:00",
            "volume": 134, "min_price": 78, "max_price": 90, "open_price": 80,
            "closed_price": 88, "avg_price": 84, "wa_price": 86.149, "median": 87,
            "moving_avg": 86.4, "donch_top": 95, "donch_bot": 78, "id": "x2",
        },
    ]


@pytest.fixture
def sample_orders_raw() -> list[dict]:
    def order(oid, otype, plat, status):
        return {
            "id": oid, "type": otype, "platinum": plat, "quantity": 1, "perTrade": 1,
            "visible": True, "createdAt": "2020-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z", "itemId": "i1",
            "user": {"id": "u" + oid, "ingameName": "p" + oid, "reputation": 5,
                     "status": status, "platform": "pc"},
        }

    return [
        order("1", "sell", 100, "ingame"),   # live
        order("2", "sell", 90, "online"),    # live, cheapest live sell
        order("3", "sell", 50, "offline"),   # cheap but NOT live -> ignored for headline
        order("4", "buy", 70, "online"),     # live buy
        order("5", "buy", 60, "offline"),    # ignored
    ]


@pytest.fixture
def sample_riven_attr_raw() -> dict:
    return {
        "id": "5c5ca81a96e8d2003834fe78",
        "slug": "punch_through",
        "gameRef": "WeaponPunctureDepthMod",
        "group": "default",
        "prefix": "Lexi",
        "suffix": "Nok",
        "i18n": {"en": {"name": "Punch Through"}},
    }


@pytest.fixture
def sample_auction_raw() -> dict:
    return {
        "id": "684b0f8fe3a05e0037564679",
        "starting_price": 40,
        "buyout_price": 40,
        "top_bid": None,
        "is_direct_sell": True,
        "visible": True,
        "closed": False,
        "owner": {"status": "ingame", "reputation": 7, "ingame_name": "Midasxo"},
        "item": {
            "re_rolls": 0,
            "name": "lexilis",
            "weapon_url_name": "kulstar",
            "mastery_level": 13,
            "mod_rank": 0,
            "polarity": "madurai",
            "type": "riven",
            "attributes": [
                {"value": 13.4, "positive": True, "url_name": "zoom"},
                {"value": -8.6, "positive": False, "url_name": "impact_damage"},
            ],
        },
    }


@pytest.fixture
def sample_void_trader_raw() -> dict:
    return {
        "character": "Baro Ki'Teer",
        "location": "Orcus Relay (Pluto)",
        "activation": "2026-06-26T13:00:00.000Z",
        "expiry": "2026-06-28T13:00:00.000Z",
        "inventory": [
            {"item": "Primed Continuity", "ducats": 350, "credits": 200000},
            {"item": "Prisma Grakata", "ducats": 600, "credits": 300000},
        ],
    }


@pytest.fixture
def sample_resurgence_raw() -> dict:
    return {
        "character": "Varzia",
        "location": "Maroo's Bazaar (Mars)",
        "activation": "2026-06-11T18:00:00.000Z",
        "expiry": "2026-07-09T18:00:00.000Z",
        "inventory": [
            {
                "uniqueName": "/Lotus/StoreItems/Powersuits/YinYang/EquinoxPrime",
                "item": "Equinox Prime", "ducats": 3, "credits": None,
            },
            {
                "uniqueName": "/Lotus/Types/StoreItems/Packages/MegaPrimeVault/MPVPack",
                "item": "M P V Equinox Prime Single Pack", "ducats": 6, "credits": None,
            },
        ],
    }


@pytest.fixture
def storage() -> Storage:
    s = Storage(":memory:")
    yield s
    s.close()
