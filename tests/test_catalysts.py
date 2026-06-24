from __future__ import annotations

from datetime import UTC, datetime

from voidbroker.catalysts import resurgence_status, void_trader_status
from voidbroker.worldstate import ResurgenceState, VoidTraderState


def _state():
    return VoidTraderState.from_api(
        {
            "character": "Baro Ki'Teer",
            "location": "Orcus Relay (Pluto)",
            "activation": "2026-06-26T13:00:00.000Z",
            "expiry": "2026-06-28T13:00:00.000Z",
            "inventory": [{"item": "Primed Continuity", "ducats": 350, "credits": 200000}],
        }
    )


def test_status_incoming_before_arrival():
    now = datetime(2026, 6, 25, 13, 0, tzinfo=UTC)  # 24h before arrival
    status = void_trader_status(_state(), now)
    assert status.phase == "incoming"
    assert status.hours_until_arrival == 24.0
    assert status.hours_until_departure is None


def test_status_active_during_visit():
    now = datetime(2026, 6, 27, 13, 0, tzinfo=UTC)  # mid-visit
    status = void_trader_status(_state(), now)
    assert status.phase == "active"
    assert status.hours_until_departure == 24.0
    assert status.inventory_size == 1


def test_status_unknown_after_departure():
    now = datetime(2026, 6, 29, 13, 0, tzinfo=UTC)  # after expiry
    status = void_trader_status(_state(), now)
    assert status.phase == "unknown"


def _resurgence():
    return ResurgenceState.from_api(
        {
            "character": "Varzia",
            "location": "Maroo's Bazaar (Mars)",
            "activation": "2026-06-11T18:00:00.000Z",
            "expiry": "2026-07-09T18:00:00.000Z",
            "inventory": [
                {"item": "Equinox Prime", "ducats": 3,
                 "uniqueName": "/Lotus/StoreItems/Powersuits/YinYang/EquinoxPrime"},
                {"item": "M P V Equinox Prime Single Pack", "ducats": 6,
                 "uniqueName": "/Lotus/Types/StoreItems/Packages/MegaPrimeVault/X"},
            ],
        }
    )


def test_resurgence_active_counts_only_non_packs():
    now = datetime(2026, 6, 20, tzinfo=UTC)  # within the window
    status = resurgence_status(_resurgence(), now)
    assert status.phase == "active"
    assert status.item_count == 1  # the pack is excluded
    assert status.hours_until_rotation is not None and status.hours_until_rotation > 0


def test_resurgence_upcoming_and_unknown():
    upcoming = resurgence_status(_resurgence(), datetime(2026, 6, 1, tzinfo=UTC))
    assert upcoming.phase == "upcoming"
    assert upcoming.hours_until_start is not None
    over = resurgence_status(_resurgence(), datetime(2026, 8, 1, tzinfo=UTC))
    assert over.phase == "unknown"
