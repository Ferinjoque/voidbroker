from __future__ import annotations

from voidbroker.vault import match_resurgence, normalize, target_set_name


def test_target_set_name_handles_word_order_and_suffixes():
    assert target_set_name("Equinox Prime") == "equinox prime set"
    assert target_set_name("Prime Stradavar Gun") == "stradavar prime set"
    assert target_set_name("Tipedo Prime Weapon") == "tipedo prime set"
    assert target_set_name("Prime Zhuge Crossbow") == "zhuge prime set"


def test_target_set_name_skips_non_sets():
    for cosmetic in [
        "Prime Cape Equinox", "Prime Wukong Syandana", "Ephemera Prime A",
        "Equinox Prime Bobble Head", "T1 Void Projection Wukong Equinox Vault A Bronze",
        "M P V Equinox Prime Single Pack",
    ]:
        assert target_set_name(cosmetic) is None


def test_normalize_is_stable():
    assert normalize("Stradavar Prime Set") == "stradavar prime set"
    assert normalize("  Equinox   Prime  Set ") == "equinox prime set"


def test_match_resurgence_exact_only():
    catalog = {
        "equinox prime set": "equinox_prime_set",
        "stradavar prime set": "stradavar_prime_set",
        "tipedo prime set": "tipedo_prime_set",
    }
    items = [
        "Equinox Prime",            # -> equinox_prime_set
        "Prime Stradavar Gun",      # -> stradavar_prime_set
        "Prime Cape Equinox",       # cosmetic -> skip
        "Nezha Prime",              # not in catalog -> unmatched
    ]
    matched = match_resurgence(items, catalog)
    assert matched == {
        "Equinox Prime": "equinox_prime_set",
        "Prime Stradavar Gun": "stradavar_prime_set",
    }


def test_match_resurgence_never_mislinks_missing():
    # A plausible base whose set isn't in the catalog must stay unmatched, not guess.
    assert match_resurgence(["Wukong Prime"], {"equinox prime set": "x"}) == {}
