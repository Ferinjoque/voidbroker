from __future__ import annotations

import httpx
import respx

from voidbroker.ingest import sync_resurgence, sync_void_trader
from voidbroker.worldstate import (
    ResurgenceState,
    VoidTraderState,
    fetch_resurgence,
    fetch_void_trader,
)


def test_void_trader_state_from_api(sample_void_trader_raw):
    state = VoidTraderState.from_api(sample_void_trader_raw)
    assert state.character == "Baro Ki'Teer"
    assert len(state.inventory) == 2
    assert state.inventory[0].ducats == 350
    assert state.activation.year == 2026


@respx.mock
async def test_fetch_void_trader(sample_void_trader_raw):
    respx.get("https://api.warframestat.us/pc/voidTrader").mock(
        return_value=httpx.Response(200, json=sample_void_trader_raw)
    )
    state = await fetch_void_trader(platform="pc")
    assert state.location == "Orcus Relay (Pluto)"


@respx.mock
async def test_sync_void_trader_persists(storage, sample_void_trader_raw):
    respx.get("https://api.warframestat.us/pc/voidTrader").mock(
        return_value=httpx.Response(200, json=sample_void_trader_raw)
    )
    ok = await sync_void_trader(storage, platform="pc")
    assert ok is True
    assert storage.count("void_trader_snapshots") == 1
    rebuilt = storage.latest_void_trader()
    assert rebuilt.character == "Baro Ki'Teer"
    assert len(rebuilt.inventory) == 2


def test_resurgence_state_from_api_and_is_pack(sample_resurgence_raw):
    state = ResurgenceState.from_api(sample_resurgence_raw)
    assert state.character == "Varzia"
    assert len(state.inventory) == 2
    assert state.inventory[0].is_pack is False
    assert state.inventory[1].is_pack is True
    assert state.inventory[0].ducats == 3


@respx.mock
async def test_fetch_resurgence(sample_resurgence_raw):
    respx.get("https://api.warframestat.us/pc/vaultTrader").mock(
        return_value=httpx.Response(200, json=sample_resurgence_raw)
    )
    state = await fetch_resurgence(platform="pc")
    assert state.character == "Varzia"
    assert state.inventory[0].item == "Equinox Prime"


@respx.mock
async def test_sync_resurgence_persists_and_roundtrips(storage, sample_resurgence_raw):
    respx.get("https://api.warframestat.us/pc/vaultTrader").mock(
        return_value=httpx.Response(200, json=sample_resurgence_raw)
    )
    ok = await sync_resurgence(storage, platform="pc")
    assert ok is True
    assert storage.count("resurgence_snapshots") == 1
    rebuilt = storage.latest_resurgence()
    assert rebuilt.character == "Varzia"
    assert len(rebuilt.inventory) == 2
    assert rebuilt.inventory[1].is_pack is True
