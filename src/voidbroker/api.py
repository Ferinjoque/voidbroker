"""FastAPI read API over the local archive — the frontend terminal talks to this.

Endpoints are ``async`` and call the (fast, local) DuckDB layer directly, which keeps
access serialized on the event loop thread and avoids cross-thread connection misuse.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .arbitrage import rank_ducat_efficiency, set_arbitrage
from .backtest import backtest_disposition, backtest_reversion, report_to_dict
from .catalysts import resurgence_status, void_trader_status
from .config import Settings, get_settings
from .digest import build_digest
from .journal import compute_journal, summary_to_dict
from .predict import rank_forecasts, to_dict
from .rivens import find_undervalued
from .signals import detect_disposition_changes, rank_opportunities
from .storage import Storage

# warframe.market slugs (url_name) are lowercase alphanumeric with underscores, and a few
# weapon slugs use hyphens. Reject anything else at the boundary so a malformed/oversized
# path segment never reaches the DB layer or gets echoed back in a 404, and never pollutes
# fetch_state on a downstream fetch.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,119}$")


def _valid_slug(slug: str) -> str:
    if not _SLUG_RE.match(slug):
        raise HTTPException(422, "Invalid slug format")
    return slug


class TradeIn(BaseModel):
    """A logged trade. Validated at the boundary before it touches the archive."""

    slug: str = Field(min_length=1, max_length=120)
    side: Literal["buy", "sell"]
    quantity: int = Field(ge=1, le=100_000)
    price: float = Field(ge=0, le=1_000_000)
    note: str | None = Field(default=None, max_length=280)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.storage = Storage(settings.db_path)
        app.state.cache = {}
        try:
            yield
        finally:
            app.state.storage.close()

    app = FastAPI(title="voidbroker", version="0.1.0", lifespan=lifespan)

    # The heavy signal endpoints recompute the same result until the next ingest (~6h), so
    # cache them in-process for a few minutes. Repeat navigations return instantly.
    cache_ttl = 300.0
    cache_max = 64  # bound the cache so parameterised keys can't grow it without limit

    def cached(key: str, compute: Callable[[], object]) -> object:
        now = time.monotonic()
        hit = app.state.cache.get(key)
        if hit and now - hit[1] < cache_ttl:
            return hit[0]
        value = compute()
        cache = app.state.cache
        if len(cache) >= cache_max and key not in cache:
            del cache[min(cache, key=lambda k: cache[k][1])]  # evict oldest
        cache[key] = (value, now)
        return value

    def cached_prices(min_volume: float = 1.0) -> dict:
        """Shared latest-price map (full price_history scan), cached so arbitrage / ducats /
        journal don't each rescan ~217k rows."""
        return cached(f"latest_prices:{min_volume}", lambda: store().latest_prices(min_volume))

    # The frontend dev server (Vite) is a different origin in local development.
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
    )

    def store() -> Storage:
        return app.state.storage

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/health/ingest")
    async def health_ingest() -> dict:
        """Per-source ingestion coverage and freshness (mirrors `voidbroker doctor`)."""
        return store().ingest_health()

    @app.get("/digest")
    async def digest() -> dict:
        """One cross-signal summary of what's worth acting on right now."""
        return cached("digest", lambda: build_digest(store(), datetime.now(UTC)))

    @app.get("/summary")
    async def summary() -> dict:
        # One round-trip instead of seven serial COUNT(*) statements.
        c = store().table_counts(
            "items", "riven_weapons", "price_history", "disposition_history",
            "order_snapshots", "riven_auctions", "void_trader_snapshots",
        )
        return {
            "items": c["items"],
            "riven_weapons": c["riven_weapons"],
            "price_rows": c["price_history"],
            "disposition_rows": c["disposition_history"],
            "order_snapshots": c["order_snapshots"],
            "riven_auctions": c["riven_auctions"],
            "void_trader_snapshots": c["void_trader_snapshots"],
        }

    @app.get("/items/search")
    async def items_search(q: str, limit: int = Query(20, ge=1, le=100)) -> dict:
        if len(q.strip()) < 2:
            return {"results": []}
        return {"results": store().search_items(q.strip(), limit=limit)}

    @app.get("/items/{slug}/prices")
    async def item_prices(slug: str) -> dict:
        slug = _valid_slug(slug)
        s = store()
        series = s.price_series(slug)
        if not series:
            raise HTTPException(404, f"No price history for {slug!r}")
        meta = s.item_meta(slug) or {}
        return {
            "slug": slug,
            "name": meta.get("name"),
            "thumb": meta.get("thumb"),
            "series": series,
        }

    @app.get("/items/{slug}/orderbook")
    async def item_orderbook(slug: str) -> dict:
        slug = _valid_slug(slug)
        snap = store().latest_order_snapshot(slug)
        if snap is None:
            raise HTTPException(404, f"No order snapshot for {slug!r}")
        return snap

    @app.get("/weapons/{slug}/disposition")
    async def weapon_disposition(slug: str) -> dict:
        slug = _valid_slug(slug)
        history = store().disposition_history(slug)
        if not history:
            raise HTTPException(404, f"No disposition history for {slug!r}")
        return {"slug": slug, "history": history}

    @app.get("/leaderboard/volume")
    async def leaderboard_volume(limit: int = Query(20, ge=1, le=200)) -> dict:
        # top_by_volume scans price_history a few times; cache the max-limit result and
        # slice, so every limit shares one computation until the next ingest.
        full = cached("leaderboard-volume", lambda: store().top_by_volume(limit=200))
        return {"items": full[:limit]}

    @app.get("/signals/opportunities")
    async def opportunities(
        limit: int = Query(50, ge=1, le=200),
        min_margin_pct: float = Query(0.05, ge=0.0, le=1.0),
        baseline_days: int = Query(7, ge=1, le=90),
    ) -> dict:
        rows = store().opportunity_inputs(baseline_days=baseline_days)
        ranked = rank_opportunities(rows, min_margin_pct=min_margin_pct)
        return {"count": len(ranked), "opportunities": [vars(o) for o in ranked[:limit]]}

    @app.get("/signals/disposition-changes")
    async def disposition_changes() -> dict:
        def _run() -> list:
            histories = store().all_disposition_histories()
            return [
                vars(c)
                for slug, hist in histories.items()
                for c in detect_disposition_changes(slug, hist)
            ]

        changes = cached("disposition-changes", _run)
        return {"count": len(changes), "changes": changes}

    @app.get("/signals/disposition-forecast")
    async def disposition_forecast(
        limit: int = Query(60, ge=1, le=500),
        direction: Literal["buff", "nerf"] | None = None,
    ) -> dict:
        """Forward-looking call on which riven dispositions DE is likely to buff or nerf,
        ranked by conviction. ``direction`` filters to "buff" or "nerf"."""
        # inputs = 3 full-table scans + a window query; cache per direction.
        forecasts = cached(
            f"disposition-forecast:{direction}",
            lambda: rank_forecasts(store().disposition_forecast_inputs(), direction=direction),
        )
        return {"count": len(forecasts), "forecasts": [to_dict(f) for f in forecasts[:limit]]}

    @app.get("/signals/disposition-backtest")
    async def disposition_backtest(cases: int = Query(50, ge=0, le=500)) -> dict:
        """Walk-forward accuracy of the disposition predictor vs realized DE changes."""
        report = cached(
            "disp-backtest",
            lambda: report_to_dict(
                backtest_disposition(store().disposition_backtest_inputs()), include_cases=None
            ),
        )
        return {**report, "cases": report["cases"][:cases]}

    @app.get("/signals/opportunity-backtest")
    async def opportunity_backtest(
        dip_pct: float = Query(0.08, ge=0.0, le=0.9),
        horizon: int = Query(7, ge=1, le=60),
    ) -> dict:
        key = f"opp-backtest:{dip_pct}:{horizon}"

        def _run() -> dict:
            rows = store().reversion_backtest_inputs()
            return vars(backtest_reversion(rows, dip_pct=dip_pct, horizon=horizon))

        return cached(key, _run)

    def _compute_riven_deals(
        min_comparables: int, min_discount: float, positives_only: bool
    ) -> list:
        s = store()
        names = s.riven_weapon_names()
        deals = []
        for weapon, auctions in s.all_latest_riven_auctions().items():
            deals.extend(
                find_undervalued(
                    weapon, auctions,
                    min_comparables=min_comparables, min_discount=min_discount,
                    positives_only=positives_only,
                )
            )
        deals.sort(key=lambda d: d.score, reverse=True)
        out = []
        for d in deals:
            row = vars(d)
            row["weapon_name"] = names.get(d.weapon_slug)
            out.append(row)
        return out

    @app.get("/signals/riven-deals")
    async def riven_deals(
        limit: int = Query(50, ge=1, le=300),
        min_comparables: int = Query(4, ge=1, le=100),
        min_discount: float = Query(0.25, ge=0.0, le=1.0),
        positives_only: bool = False,
    ) -> dict:
        key = f"riven-deals:{min_comparables}:{min_discount}:{positives_only}"
        full = cached(
            key, lambda: _compute_riven_deals(min_comparables, min_discount, positives_only)
        )
        return {"count": len(full), "deals": full[:limit]}

    @app.get("/signals/set-arbitrage")
    async def set_arbitrage_signal(
        limit: int = Query(50, ge=1, le=300), min_margin: float = Query(0.10, ge=0.0, le=5.0)
    ) -> dict:
        """Sets whose price diverges from their summed part prices (build/split flips)."""
        key = f"set-arb:{min_margin}"
        full = cached(
            key,
            lambda: [
                vars(a)
                for a in set_arbitrage(
                    store().set_arbitrage_inputs(prices=cached_prices()), min_margin
                )
            ],
        )
        return {"count": len(full), "deals": full[:limit]}

    @app.get("/signals/ducats")
    async def ducat_efficiency(
        limit: int = Query(50, ge=1, le=300), min_ducats: int = Query(15, ge=0, le=1000)
    ) -> dict:
        """Items ranked by ducats-per-platinum — cheapest plat→ducat conversion for Baro."""
        key = f"ducats:{min_ducats}"

        def _run() -> list:
            rows = store().ducat_efficiency_inputs(prices=cached_prices())
            return [vars(d) for d in rank_ducat_efficiency(rows, min_ducats)]

        full = cached(key, _run)
        return {"count": len(full), "items": full[:limit]}

    @app.get("/rivens/{weapon}/auctions")
    async def riven_auctions(weapon: str) -> dict:
        weapon = _valid_slug(weapon)
        auctions = store().latest_riven_auctions(weapon)
        if not auctions:
            raise HTTPException(404, f"No riven auctions stored for {weapon!r}")
        return {"weapon": weapon, "auctions": [a.model_dump() for a in auctions]}

    @app.get("/catalysts/void-trader")
    async def catalyst_void_trader() -> dict:
        state = store().latest_void_trader()
        if state is None:
            raise HTTPException(404, "No void trader snapshot yet")
        status = void_trader_status(state, datetime.now(UTC))
        return {"status": vars(status), "inventory": [i.model_dump() for i in state.inventory]}

    @app.get("/catalysts/resurgence")
    async def catalyst_resurgence() -> dict:
        s = store()
        state = s.latest_resurgence()
        if state is None:
            raise HTTPException(404, "No resurgence snapshot yet")
        status = resurgence_status(state, datetime.now(UTC))
        return {
            "status": vars(status),
            "inventory": [i.model_dump() for i in state.inventory],
            # status is time-dependent (recomputed each call); the price-impact scan is not.
            "impact": cached("resurgence-impact", s.resurgence_price_impact),
        }

    # --- trade journal (the only mutating endpoints; local single-user app) -------

    @app.get("/journal")
    async def journal() -> dict:
        """Realized + unrealized P&L from logged trades, plus open positions and the log."""
        s = store()
        trades = s.list_trades()
        # Cached price map (you may hold illiquid items, so price all of them: min_volume=0).
        prices = cached_prices(min_volume=0.0)
        summary = summary_to_dict(compute_journal(trades, prices))
        return {"summary": summary, "trades": trades}

    @app.post("/trades")
    async def add_trade(trade: TradeIn) -> dict:
        s = store()
        if s.item_meta(trade.slug) is None:
            raise HTTPException(404, f"Unknown item slug {trade.slug!r}")
        tid = s.record_trade(trade.slug, trade.side, trade.quantity, trade.price, trade.note)
        return {"id": tid}

    @app.delete("/trades/{trade_id}")
    async def delete_trade(trade_id: int) -> dict:
        if not store().delete_trade(trade_id):
            raise HTTPException(404, f"No trade #{trade_id}")
        return {"deleted": trade_id}

    return app


app = create_app()
