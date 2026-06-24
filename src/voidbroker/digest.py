"""The digest, one "what should I act on right now" view over every signal layer.

A compounding archive is only useful if it surfaces the few things worth acting on today.
This orchestrates the existing signal layers (opportunities, quality riven deals, imminent
disposition moves, the resurgence buy-window, Baro) into a single ranked summary. It's an
orchestration layer (it touches storage), not pure logic, so it lives apart from the pure
signal modules and is shared by the CLI and the API.
"""

from __future__ import annotations

from datetime import datetime

from .catalysts import resurgence_status, void_trader_status
from .predict import rank_forecasts, to_dict
from .rivens import find_undervalued
from .signals import rank_opportunities
from .storage import Storage

# Only surface riven deals whose roll is at least average, a cheap weak roll isn't a steal.
_MIN_ROLL_QUALITY = 0.5


def build_digest(storage: Storage, now: datetime, *, per_section: int = 5) -> dict:
    """Assemble the cross-signal digest. Each section is capped at ``per_section`` items."""
    opportunities = [
        vars(o) for o in rank_opportunities(storage.opportunity_inputs())[:per_section]
    ]

    names = storage.riven_weapon_names()
    deals = []
    for weapon, auctions in storage.all_latest_riven_auctions().items():
        deals.extend(find_undervalued(weapon, auctions, positives_only=True))
    deals = [d for d in deals if d.roll_quality >= _MIN_ROLL_QUALITY]
    deals.sort(key=lambda d: d.score, reverse=True)
    riven_deals = []
    for d in deals[:per_section]:
        row = vars(d)
        row["weapon_name"] = names.get(d.weapon_slug)
        riven_deals.append(row)

    forecasts = [
        to_dict(f)
        for f in rank_forecasts(storage.disposition_forecast_inputs())
        if f.direction != "stable"
    ][:per_section]

    res = storage.latest_resurgence()
    resurgence = None
    if res is not None:
        impact = storage.resurgence_price_impact()
        resurgence = {
            "status": vars(resurgence_status(res, now)),
            "best_buys": impact[:per_section],  # already sorted biggest-dip-first
        }

    baro = storage.latest_void_trader()
    void_trader = vars(void_trader_status(baro, now)) if baro is not None else None

    return {
        "opportunities": opportunities,
        "riven_deals": riven_deals,
        "disposition_forecasts": forecasts,
        "resurgence": resurgence,
        "void_trader": void_trader,
    }
