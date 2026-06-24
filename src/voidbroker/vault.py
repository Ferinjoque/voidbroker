"""Link Prime Resurgence (Varzia) inventory names to warframe.market set slugs.

Varzia lists items with messy, inconsistent names ("Prime Stradavar Gun", "Equinox Prime",
"Tipedo Prime Weapon") and mixes in cosmetics, relics and bundle packs that aren't tradable
as sets. The market sells the canonical "X Prime Set". This reduces each inventory name to
its base and matches it to a set slug, but only on an *exact* normalized match — so it
leaves an entry unmatched rather than mislinking it. Pure functions, no I/O.
"""

from __future__ import annotations

import re

# Inventory entries that are never a tradable "X Prime Set" (cosmetics, relics, packs).
_SKIP = {
    "cape", "syandana", "ephemera", "bobble", "sigil", "scene", "noggle", "glyph",
    "projection", "relic", "pack", "package", "captura", "display", "accessories",
    "armor", "armour", "sugatra", "emblem", "badge",
}
# Weapon-class / filler words dropped when reducing a name to its base.
_DROP = {
    "prime", "set", "gun", "weapon", "crossbow", "pistol", "rifle", "shotgun", "bow",
    "blade", "sword", "hammer", "staff", "scythe", "dagger", "glaive", "whip", "claws",
    "gauntlet", "fist", "nunchaku", "blueprint", "kit", "warframe", "the",
}


def _tokens(name: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]", " ", name.lower()).split()


def normalize(name: str) -> str:
    """Canonical comparable form: lowercase, alphanumerics, single-spaced."""
    return " ".join(_tokens(name))


def target_set_name(item: str) -> str | None:
    """The market set name a Varzia entry should map to, or None if it isn't a set.

    "Prime Stradavar Gun" -> "stradavar prime set"; "Equinox Prime" -> "equinox prime set".
    Cosmetics / relics / packs return None.
    """
    toks = _tokens(item)
    if not toks or any(t in _SKIP for t in toks):
        return None
    base = [t for t in toks if t not in _DROP]
    if not base:
        return None
    return f"{' '.join(base)} prime set"


def match_resurgence(item_names: list[str], catalog_by_name: dict[str, str]) -> dict[str, str]:
    """Map inventory item names to set slugs. ``catalog_by_name`` is NORMALIZED market name
    -> slug. Only exact target matches are returned, keyed by the original item name."""
    out: dict[str, str] = {}
    for item in item_names:
        target = target_set_name(item)
        if target and target in catalog_by_name:
            out[item] = catalog_by_name[target]
    return out
