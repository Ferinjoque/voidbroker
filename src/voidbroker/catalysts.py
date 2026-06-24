"""Catalyst signals, turning scheduled worldstate events into actionable status.

Pure functions: callers pass ``now`` so behavior is deterministic and testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .worldstate import ResurgenceState, VoidTraderState


@dataclass(frozen=True)
class VoidTraderStatus:
    character: str | None
    location: str | None
    phase: str            # "active" | "incoming" | "unknown"
    hours_until_arrival: float | None
    hours_until_departure: float | None
    inventory_size: int


def void_trader_status(state: VoidTraderState, now: datetime) -> VoidTraderStatus:
    """Classify Baro's current phase and the countdown that matters for it.

    ``active``  → he's here now; report hours until he leaves (last chance to buy).
    ``incoming`` → he's scheduled; report hours until arrival (time to stockpile ducats /
    position around the items he'll carry).
    """
    activation = state.activation
    expiry = state.expiry

    def hours(delta) -> float:
        return round(delta.total_seconds() / 3600.0, 2)

    if activation and expiry and activation <= now < expiry:
        phase = "active"
        until_departure = hours(expiry - now)
        until_arrival = None
    elif activation and now < activation:
        phase = "incoming"
        until_arrival = hours(activation - now)
        until_departure = None
    else:
        phase = "unknown"
        until_arrival = None
        until_departure = None

    return VoidTraderStatus(
        character=state.character,
        location=state.location,
        phase=phase,
        hours_until_arrival=until_arrival,
        hours_until_departure=until_departure,
        inventory_size=len(state.inventory),
    )


@dataclass(frozen=True)
class ResurgenceStatus:
    character: str | None
    phase: str                       # "active" | "upcoming" | "unknown"
    hours_until_rotation: float | None  # until the current offerings re-vault
    hours_until_start: float | None
    item_count: int                  # individually tradable items (packs excluded)


def resurgence_status(state: ResurgenceState, now: datetime) -> ResurgenceStatus:
    """Classify the current Prime Resurgence window and the countdown that matters.

    ``active``   → these Primes are buyable now; report hours until they re-vault (the buy
    window, supply is up and plat is soft, so this is the moment to accumulate).
    ``upcoming`` → a rotation is scheduled; report hours until it starts.
    """
    activation = state.activation
    expiry = state.expiry

    def hours(delta) -> float:
        return round(delta.total_seconds() / 3600.0, 2)

    if activation and expiry and activation <= now < expiry:
        phase = "active"
        until_rotation = hours(expiry - now)
        until_start = None
    elif activation and now < activation:
        phase = "upcoming"
        until_start = hours(activation - now)
        until_rotation = None
    else:
        phase = "unknown"
        until_rotation = None
        until_start = None

    return ResurgenceStatus(
        character=state.character,
        phase=phase,
        hours_until_rotation=until_rotation,
        hours_until_start=until_start,
        item_count=sum(1 for i in state.inventory if not i.is_pack),
    )
