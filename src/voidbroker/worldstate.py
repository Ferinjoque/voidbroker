"""Worldstate catalysts, scheduled events that move prices.

Baro Ki'Teer (the "void trader") arrives roughly every two weeks selling otherwise
unobtainable items for ducats + credits. His arrival and inventory are a known, scheduled
catalyst: items he carries (primed mods, exclusive cosmetics) see predictable demand
swings around the visit. We snapshot his state from WFCD's parsed worldstate API.

This is a separate host from warframe.market, so it has its own tiny fetcher rather than
reusing the market client.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel, Field

WORLDSTATE_BASE = "https://api.warframestat.us"

# platform is interpolated into the outbound URL path. Settings validates it at load, but
# these fetchers take a raw str default, so re-check here: a stray value can't redirect or
# malform the request (httpx follows redirects by default).
_PLATFORMS = frozenset({"pc", "ps4", "xbox", "switch", "mobile"})


def _check_platform(platform: str) -> str:
    if platform not in _PLATFORMS:
        raise ValueError(f"platform must be one of {sorted(_PLATFORMS)}")
    return platform


class VoidTraderItem(BaseModel):
    item: str
    ducats: int = 0
    credits: int = 0

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> VoidTraderItem:
        return cls(
            item=raw.get("item", ""),
            ducats=raw.get("ducats") or 0,
            credits=raw.get("credits") or 0,
        )


class VoidTraderState(BaseModel):
    character: str | None = None
    location: str | None = None
    activation: datetime | None = None
    expiry: datetime | None = None
    inventory: list[VoidTraderItem] = Field(default_factory=list)

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> VoidTraderState:
        return cls(
            character=raw.get("character"),
            location=raw.get("location"),
            activation=raw.get("activation"),
            expiry=raw.get("expiry"),
            inventory=[VoidTraderItem.from_api(i) for i in raw.get("inventory", [])],
        )


async def fetch_void_trader(
    platform: str = "pc",
    base: str = WORLDSTATE_BASE,
    client: httpx.AsyncClient | None = None,
) -> VoidTraderState:
    platform = _check_platform(platform)
    owns = client is None
    client = client or httpx.AsyncClient(timeout=30.0)
    try:
        resp = await client.get(
            f"{base}/{platform}/voidTrader", headers={"accept": "application/json"}
        )
        resp.raise_for_status()
        return VoidTraderState.from_api(resp.json())
    finally:
        if owns:
            await client.aclose()


# ── Prime Resurgence (Varzia / the "vault trader") ────────────────────────────
# Varzia rotates a set of otherwise-vaulted Prime items into temporary availability for
# Aya/Regal Aya. While an item is in resurgence its market supply rises and plat price
# softens; once it re-vaults, scarcity pushes the price back up. So "what's resurged now,
# and when does the window close" is a buy-now-hold signal, the inverse of Baro.


class ResurgenceItem(BaseModel):
    item: str
    ducats: int = 0
    unique_name: str | None = None

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> ResurgenceItem:
        return cls(
            item=raw.get("item", ""),
            ducats=raw.get("ducats") or 0,
            unique_name=raw.get("uniqueName"),
        )

    @property
    def is_pack(self) -> bool:
        """Bundle packages (vs. individually tradable items), heuristic on the path/name."""
        u = (self.unique_name or "").lower()
        return "package" in u or "pack" in self.item.lower()


class ResurgenceState(BaseModel):
    character: str | None = None
    location: str | None = None
    activation: datetime | None = None
    expiry: datetime | None = None
    inventory: list[ResurgenceItem] = Field(default_factory=list)

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> ResurgenceState:
        return cls(
            character=raw.get("character"),
            location=raw.get("location"),
            activation=raw.get("activation"),
            expiry=raw.get("expiry"),
            inventory=[ResurgenceItem.from_api(i) for i in raw.get("inventory", [])],
        )


async def fetch_resurgence(
    platform: str = "pc",
    base: str = WORLDSTATE_BASE,
    client: httpx.AsyncClient | None = None,
) -> ResurgenceState:
    """Snapshot Varzia's current Prime Resurgence offerings from WFCD's vaultTrader feed."""
    platform = _check_platform(platform)
    owns = client is None
    client = client or httpx.AsyncClient(timeout=30.0)
    try:
        resp = await client.get(
            f"{base}/{platform}/vaultTrader", headers={"accept": "application/json"}
        )
        resp.raise_for_status()
        return ResurgenceState.from_api(resp.json())
    finally:
        if owns:
            await client.aclose()
