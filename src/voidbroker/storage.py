"""DuckDB-backed local archive.

Single file, no server. Holds the catalog plus three time series that accumulate on
every ingest and form voidbroker's moat:

* ``price_history``      , daily candlesticks (bootstrapped from the 90d statistics feed)
* ``disposition_history``, riven disposition over time (the predictor's training data)
* ``order_snapshots``    , point-in-time live order-book aggregates (liquidity)
"""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from .metrics import OrderBookSnapshot
from .models import (
    Item,
    ItemDetail,
    RivenAttribute,
    RivenAuction,
    RivenStat,
    RivenWeapon,
    StatRecord,
)
from .vault import match_resurgence, normalize
from .worldstate import ResurgenceState, VoidTraderState

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id          VARCHAR PRIMARY KEY,
    slug        VARCHAR NOT NULL,
    name        VARCHAR,
    game_ref    VARCHAR,
    tags        VARCHAR[],
    is_riven    BOOLEAN,
    thumb       VARCHAR,
    first_seen  TIMESTAMPTZ,
    last_seen   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS item_details (
    slug        VARCHAR PRIMARY KEY,
    ducats      INTEGER,
    trading_tax INTEGER,
    set_root    BOOLEAN,
    set_parts   VARCHAR[],
    tradable    BOOLEAN,
    captured_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS riven_weapons (
    id               VARCHAR PRIMARY KEY,
    slug             VARCHAR NOT NULL,
    name             VARCHAR,
    weapon_group     VARCHAR,
    riven_type       VARCHAR,
    req_mastery_rank INTEGER,
    last_seen        TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS disposition_history (
    weapon_slug VARCHAR NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    disposition DOUBLE,
    PRIMARY KEY (weapon_slug, captured_at)
);

CREATE TABLE IF NOT EXISTS price_history (
    slug        VARCHAR NOT NULL,
    datetime    TIMESTAMPTZ NOT NULL,
    volume      BIGINT,
    min_price   DOUBLE,
    max_price   DOUBLE,
    open_price  DOUBLE,
    closed_price DOUBLE,
    avg_price   DOUBLE,
    wa_price    DOUBLE,
    median      DOUBLE,
    moving_avg  DOUBLE,
    donch_top   DOUBLE,
    donch_bot   DOUBLE,
    PRIMARY KEY (slug, datetime)
);

CREATE TABLE IF NOT EXISTS order_snapshots (
    slug         VARCHAR NOT NULL,
    captured_at  TIMESTAMPTZ NOT NULL,
    sell_min     DOUBLE,
    sell_p25     DOUBLE,
    sell_median  DOUBLE,
    buy_max      DOUBLE,
    spread       DOUBLE,
    n_sell_live  INTEGER,
    n_buy_live   INTEGER,
    n_sell_total INTEGER,
    n_buy_total  INTEGER,
    PRIMARY KEY (slug, captured_at)
);

CREATE TABLE IF NOT EXISTS riven_attributes (
    id         VARCHAR PRIMARY KEY,
    slug       VARCHAR NOT NULL,
    attr_group VARCHAR,
    prefix     VARCHAR,
    suffix     VARCHAR,
    name       VARCHAR,
    last_seen  TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS riven_auctions (
    auction_id      VARCHAR NOT NULL,
    captured_at     TIMESTAMPTZ NOT NULL,
    weapon_slug     VARCHAR NOT NULL,
    starting_price  DOUBLE,
    buyout_price    DOUBLE,
    top_bid         DOUBLE,
    is_direct_sell  BOOLEAN,
    re_rolls        INTEGER,
    mod_rank        INTEGER,
    mastery_level   INTEGER,
    polarity        VARCHAR,
    owner_status    VARCHAR,
    owner_reputation INTEGER,
    visible         BOOLEAN,
    closed          BOOLEAN,
    attributes_json VARCHAR,
    PRIMARY KEY (auction_id, captured_at)
);

CREATE TABLE IF NOT EXISTS void_trader_snapshots (
    captured_at    TIMESTAMPTZ PRIMARY KEY,
    character      VARCHAR,
    location       VARCHAR,
    activation     TIMESTAMPTZ,
    expiry         TIMESTAMPTZ,
    inventory_size INTEGER,
    inventory_json VARCHAR
);

CREATE TABLE IF NOT EXISTS resurgence_snapshots (
    captured_at    TIMESTAMPTZ PRIMARY KEY,
    character      VARCHAR,
    location       VARCHAR,
    activation     TIMESTAMPTZ,
    expiry         TIMESTAMPTZ,
    inventory_size INTEGER,
    inventory_json VARCHAR
);

CREATE TABLE IF NOT EXISTS fetch_state (
    source     VARCHAR NOT NULL,   -- 'prices' | 'orders' | 'auctions'
    ref        VARCHAR NOT NULL,   -- item or weapon slug
    last_fetch TIMESTAMPTZ,
    ok         BOOLEAN,
    error      VARCHAR,
    PRIMARY KEY (source, ref)
);

CREATE TABLE IF NOT EXISTS alert_log (
    key             VARCHAR PRIMARY KEY,
    kind            VARCHAR,
    title           VARCHAR,
    last_alerted_at TIMESTAMPTZ
);

CREATE SEQUENCE IF NOT EXISTS trades_id_seq START 1;
CREATE TABLE IF NOT EXISTS trades (
    id        BIGINT PRIMARY KEY DEFAULT nextval('trades_id_seq'),
    slug      VARCHAR NOT NULL,
    side      VARCHAR NOT NULL,   -- 'buy' | 'sell'
    quantity  INTEGER NOT NULL,
    price     DOUBLE NOT NULL,    -- platinum per unit
    traded_at TIMESTAMPTZ NOT NULL,
    note      VARCHAR
);
"""

# Per-source catalog the ingester sweeps, and which table supplies the candidate refs.
FETCH_SOURCES = {
    "prices": "items",
    "orders": "items",
    "details": "items",
    "auctions": "riven_weapons",
}

# Pre-built per-source "stalest refs" queries. Static strings (no f-string over the table at
# call time) so there's no SQL interpolation to re-audit if the source param ever widens.
_STALEST_SQL = {
    source: f"""
        SELECT t.slug
        FROM {table} t
        LEFT JOIN fetch_state f ON f.source = ? AND f.ref = t.slug
        ORDER BY f.last_fetch ASC NULLS FIRST, t.slug
        LIMIT ?
    """
    for source, table in FETCH_SOURCES.items()
}


def _utcnow() -> datetime:
    return datetime.now(UTC)


# Latest snapshot per auction. Two fully-static variants (no interpolation) selected by
# `all_latest_riven_auctions(live_only=...)`.
_RIVEN_AUCTIONS_ALL_SQL = """
    SELECT * FROM (
        SELECT * FROM riven_auctions
        QUALIFY row_number() OVER (PARTITION BY auction_id ORDER BY captured_at DESC) = 1
    ) latest
"""
_RIVEN_AUCTIONS_LIVE_SQL = (
    _RIVEN_AUCTIONS_ALL_SQL
    + "WHERE visible AND NOT closed AND owner_status IN ('online', 'ingame')"
)


class Storage:
    """Thin, typed wrapper over a DuckDB connection."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        if self.db_path != ":memory:":
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(self.db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        self.con.execute(_SCHEMA)
        # Migrations for archives created before a column existed (idempotent).
        self.con.execute("ALTER TABLE items ADD COLUMN IF NOT EXISTS thumb VARCHAR")

    def close(self) -> None:
        self.con.close()

    def __enter__(self) -> Storage:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # --- writes ------------------------------------------------------------------

    def upsert_items(self, items: list[Item], now: datetime | None = None) -> int:
        now = now or _utcnow()
        rows = [
            (it.id, it.slug, it.name, it.game_ref, it.tags, it.is_riven, it.thumb, now, now)
            for it in items
        ]
        self.con.executemany(
            """
            INSERT INTO items
                (id, slug, name, game_ref, tags, is_riven, thumb, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                slug = excluded.slug,
                name = excluded.name,
                game_ref = excluded.game_ref,
                tags = excluded.tags,
                is_riven = excluded.is_riven,
                thumb = excluded.thumb,
                last_seen = excluded.last_seen
            """,
            rows,
        )
        return len(rows)

    def upsert_item_details(self, details: list[ItemDetail], now: datetime | None = None) -> int:
        now = now or _utcnow()
        rows = [
            (d.slug, d.ducats, d.trading_tax, d.set_root, d.set_parts, d.tradable, now)
            for d in details
        ]
        if rows:
            self.con.executemany(
                """
                INSERT INTO item_details
                    (slug, ducats, trading_tax, set_root, set_parts, tradable, captured_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (slug) DO UPDATE SET
                    ducats = excluded.ducats,
                    trading_tax = excluded.trading_tax,
                    set_root = excluded.set_root,
                    set_parts = excluded.set_parts,
                    tradable = excluded.tradable,
                    captured_at = excluded.captured_at
                """,
                rows,
            )
        return len(rows)

    def upsert_riven_weapons(self, weapons: list[RivenWeapon], now: datetime | None = None) -> int:
        """Upsert weapon metadata *and* append a disposition snapshot for each."""
        now = now or _utcnow()
        meta_rows = [
            (w.id, w.slug, w.name, w.group, w.riven_type, w.req_mastery_rank, now)
            for w in weapons
        ]
        self.con.executemany(
            """
            INSERT INTO riven_weapons
                (id, slug, name, weapon_group, riven_type, req_mastery_rank, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                slug = excluded.slug,
                name = excluded.name,
                weapon_group = excluded.weapon_group,
                riven_type = excluded.riven_type,
                req_mastery_rank = excluded.req_mastery_rank,
                last_seen = excluded.last_seen
            """,
            meta_rows,
        )
        disp_rows = [
            (w.slug, now, w.disposition) for w in weapons if w.disposition is not None
        ]
        if disp_rows:
            self.con.executemany(
                """
                INSERT INTO disposition_history (weapon_slug, captured_at, disposition)
                VALUES (?, ?, ?)
                ON CONFLICT (weapon_slug, captured_at) DO UPDATE SET
                    disposition = excluded.disposition
                """,
                disp_rows,
            )
        return len(meta_rows)

    def upsert_price_history(self, slug: str, records: list[StatRecord]) -> int:
        rows = [
            (
                slug, r.datetime, r.volume, r.min_price, r.max_price, r.open_price,
                r.closed_price, r.avg_price, r.wa_price, r.median, r.moving_avg,
                r.donch_top, r.donch_bot,
            )
            for r in records
        ]
        if rows:
            self.con.executemany(
                """
                INSERT INTO price_history (
                    slug, datetime, volume, min_price, max_price, open_price,
                    closed_price, avg_price, wa_price, median, moving_avg, donch_top, donch_bot
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (slug, datetime) DO UPDATE SET
                    volume = excluded.volume,
                    min_price = excluded.min_price,
                    max_price = excluded.max_price,
                    open_price = excluded.open_price,
                    closed_price = excluded.closed_price,
                    avg_price = excluded.avg_price,
                    wa_price = excluded.wa_price,
                    median = excluded.median,
                    moving_avg = excluded.moving_avg,
                    donch_top = excluded.donch_top,
                    donch_bot = excluded.donch_bot
                """,
                rows,
            )
        return len(rows)

    def record_order_snapshot(
        self, slug: str, snap: OrderBookSnapshot, now: datetime | None = None
    ) -> None:
        now = now or _utcnow()
        self.con.execute(
            """
            INSERT INTO order_snapshots (
                slug, captured_at, sell_min, sell_p25, sell_median, buy_max, spread,
                n_sell_live, n_buy_live, n_sell_total, n_buy_total
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (slug, captured_at) DO NOTHING
            """,
            [
                slug, now, snap.sell_min, snap.sell_p25, snap.sell_median, snap.buy_max,
                snap.spread, snap.n_sell_live, snap.n_buy_live, snap.n_sell_total,
                snap.n_buy_total,
            ],
        )

    # --- ingestion state (tiered, resumable sweeps) ------------------------------

    def record_fetch(
        self, source: str, ref: str, *, ok: bool = True, error: str | None = None,
        now: datetime | None = None,
    ) -> None:
        """Stamp when a ref (item/weapon) was last fetched for a source, and the outcome.

        This is what makes ingestion resumable: the scheduler can pick the *stalest* refs
        each run and rotate through the whole catalog without re-fetching fresh data.
        """
        self.con.execute(
            """
            INSERT INTO fetch_state (source, ref, last_fetch, ok, error)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (source, ref) DO UPDATE SET
                last_fetch = excluded.last_fetch,
                ok = excluded.ok,
                error = excluded.error
            """,
            [source, ref, now or _utcnow(), ok, (error or "")[:300] or None],
        )

    def stalest_refs(self, source: str, limit: int) -> list[str]:
        """The ``limit`` refs most overdue for a fetch: never-fetched first, then oldest.

        Candidates come from the catalog table mapped to the source, so a sweep only ever
        targets refs that actually exist.
        """
        sql = _STALEST_SQL.get(source)
        if sql is None:
            raise ValueError(f"Unknown fetch source: {source}")
        return [r["slug"] for r in self._rows(sql, [source, limit])]

    def ingest_health(self) -> dict:
        """Per-source coverage + freshness, for ``doctor`` / ``/health/ingest``.

        Surfaces silent starvation: how much of each catalog has ever been fetched, how
        fresh the oldest tracked ref is, and how many last attempts errored.
        """
        catalog = {
            "items": self.count("items"),
            "riven_weapons": self.count("riven_weapons"),
        }
        sources: dict[str, dict] = {}
        for source, table in FETCH_SOURCES.items():
            total = catalog["items"] if table == "items" else catalog["riven_weapons"]
            row = self._rows(
                """
                SELECT
                    count(*) AS tracked,
                    count(*) FILTER (WHERE ok) AS ok,
                    count(*) FILTER (WHERE NOT ok) AS errors,
                    min(last_fetch) AS oldest,
                    max(last_fetch) AS newest
                FROM fetch_state WHERE source = ?
                """,
                [source],
            )[0]
            tracked = row["tracked"] or 0
            sources[source] = {
                "catalog": total,
                "tracked": tracked,
                "ok": row["ok"] or 0,
                "errors": row["errors"] or 0,
                "coverage_pct": round(100 * tracked / total, 1) if total else 0.0,
                "oldest_fetch": row["oldest"],
                "newest_fetch": row["newest"],
            }
        return {"catalog": catalog, "sources": sources}

    # --- reads -------------------------------------------------------------------

    def _rows(self, sql: str, params: list[Any] | None = None) -> list[dict]:
        cur = self.con.execute(sql, params or [])
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]

    # Pre-written count statements keyed by table name. Using a static map (not an f-string
    # over a validated name) means there is no SQL interpolation to re-audit at any callsite.
    _COUNT_SQL = {
        t: f"SELECT count(*) FROM {t}"
        for t in (
            "items", "item_details", "riven_weapons", "disposition_history", "price_history",
            "order_snapshots", "riven_attributes", "riven_auctions", "void_trader_snapshots",
            "resurgence_snapshots", "fetch_state", "alert_log", "trades",
        )
    }

    def count(self, table: str) -> int:
        sql = self._COUNT_SQL.get(table)
        if sql is None:
            raise ValueError(f"Unknown table: {table}")
        return self.con.execute(sql).fetchone()[0]

    def table_counts(self, *tables: str) -> dict[str, int]:
        """Row counts for several tables in a single round-trip (vs one COUNT each)."""
        parts = []
        for t in tables:
            if t not in self._COUNT_SQL:
                raise ValueError(f"Unknown table: {t}")
            parts.append(f"(SELECT count(*) FROM {t}) AS {t}")
        cur = self.con.execute("SELECT " + ", ".join(parts))
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, cur.fetchone(), strict=True))

    def price_series(self, slug: str) -> list[dict]:
        return self._rows(
            "SELECT * FROM price_history WHERE slug = ? ORDER BY datetime", [slug]
        )

    def item_name(self, slug: str) -> str | None:
        row = self.con.execute("SELECT name FROM items WHERE slug = ?", [slug]).fetchone()
        return row[0] if row else None

    def item_meta(self, slug: str) -> dict | None:
        rows = self._rows("SELECT name, thumb FROM items WHERE slug = ?", [slug])
        return rows[0] if rows else None

    def latest_prices(self, min_volume: float = 1.0, days: int = 14) -> dict[str, float]:
        """Robust recent market price per item: median close over the last ``days``, but only
        for items that actually trade (avg daily volume >= ``min_volume``).

        Using the median (not a single ``moving_avg``) and gating on volume keeps stale
        fat-finger prices on dead items out of the arbitrage / ducat signals, those outliers
        otherwise produce absurd 1000%+ margins.
        """
        # Materialize the global max once in a CTE; the correlated form re-scanned
        # price_history to recompute max(datetime) alongside the GROUP BY (double scan).
        rows = self._rows(
            """
            WITH cutoff AS (SELECT max(datetime) - (? * INTERVAL 1 DAY) AS ts FROM price_history)
            SELECT slug, median(closed_price) AS price, avg(volume) AS vol
            FROM price_history, cutoff
            WHERE datetime >= cutoff.ts
            GROUP BY slug
            """,
            [days],
        )
        out: dict[str, float] = {}
        for r in rows:
            price, vol = r["price"], r["vol"] or 0.0
            if price and price > 0 and vol >= min_volume:
                out[r["slug"]] = round(price, 2)
        return out

    def ducat_efficiency_inputs(self, prices: dict[str, float] | None = None) -> list[dict]:
        """Tradable items with a ducat value and a market price (for ducat-per-plat ranking).

        Pass ``prices`` (from ``latest_prices``) to reuse a cached/shared price map instead of
        rescanning price_history."""
        prices = prices if prices is not None else self.latest_prices()
        rows = self._rows(
            """
            SELECT d.slug, i.name, i.thumb, d.ducats
            FROM item_details d JOIN items i ON i.slug = d.slug
            WHERE d.ducats > 0 AND d.tradable
            """
        )
        out = []
        for r in rows:
            price = prices.get(r["slug"])
            if price:
                out.append({**r, "price": price})
        return out

    def set_arbitrage_inputs(self, prices: dict[str, float] | None = None) -> list[dict]:
        """Each tradable set with its component parts and their prices, for the arbitrage scan.

        ``set_parts`` holds component item ids; resolve them to slugs via the items table.
        Pass ``prices`` to reuse a cached/shared price map instead of rescanning price_history.
        """
        prices = prices if prices is not None else self.latest_prices()
        id_map = {
            r["id"]: (r["slug"], r["name"])
            for r in self._rows("SELECT id, slug, name FROM items")
        }
        sets = self._rows(
            """
            SELECT d.slug, i.name, d.trading_tax, d.set_parts
            FROM item_details d JOIN items i ON i.slug = d.slug
            WHERE d.set_root AND d.tradable
            """
        )
        out = []
        for s in sets:
            set_price = prices.get(s["slug"])
            if not set_price:
                continue
            parts = []
            for pid in s["set_parts"] or []:
                resolved = id_map.get(pid)
                if not resolved or resolved[0] == s["slug"]:
                    continue  # unknown id, or the set root listed among its own parts
                pslug, pname = resolved
                parts.append({"slug": pslug, "name": pname, "price": prices.get(pslug)})
            out.append(
                {
                    "slug": s["slug"],
                    "name": s["name"],
                    "set_price": set_price,
                    "tax": s["trading_tax"] or 0,
                    "parts": parts,
                }
            )
        return out

    def search_items(self, q: str, limit: int = 20) -> list[dict]:
        """Case-insensitive substring search over item name and slug.

        Matches the query anywhere in the name or slug (not prefix-only), and ranks an
        actual prefix match first so the closest results surface at the top.
        """
        # Escape LIKE metacharacters so a query of "%" or "_" doesn't match everything.
        esc = q.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{esc}%"
        prefix = f"{esc}%"
        return self._rows(
            r"""
            SELECT slug, name, thumb
            FROM items
            WHERE lower(name) LIKE ? ESCAPE '\' OR lower(slug) LIKE ? ESCAPE '\'
            ORDER BY
                CASE WHEN lower(name) LIKE ? ESCAPE '\' OR lower(slug) LIKE ? ESCAPE '\'
                     THEN 0 ELSE 1 END,
                length(coalesce(name, slug)),
                name
            LIMIT ?
            """,
            [like, like, prefix, prefix, limit],
        )

    def riven_weapon_names(self) -> dict[str, str]:
        rows = self._rows("SELECT slug, name FROM riven_weapons")
        return {r["slug"]: r["name"] for r in rows if r["name"]}

    def disposition_history(self, slug: str) -> list[dict]:
        return self._rows(
            "SELECT captured_at, disposition FROM disposition_history "
            "WHERE weapon_slug = ? ORDER BY captured_at",
            [slug],
        )

    def latest_order_snapshot(self, slug: str) -> dict | None:
        rows = self._rows(
            "SELECT * FROM order_snapshots WHERE slug = ? ORDER BY captured_at DESC LIMIT 1",
            [slug],
        )
        return rows[0] if rows else None

    def top_by_volume(self, limit: int = 20, spark_days: int = 14) -> list[dict]:
        """Most-traded items by latest-day volume, each with a recent-close sparkline."""
        return self._rows(
            """
            WITH max_dt AS (SELECT max(datetime) AS d FROM price_history),
            latest AS (
                SELECT slug, max(datetime) AS d FROM price_history GROUP BY slug
            ),
            spark AS (
                SELECT slug, list(closed_price ORDER BY datetime) AS spark
                FROM price_history, max_dt
                WHERE datetime >= max_dt.d - (? * INTERVAL 1 DAY)
                GROUP BY slug
            )
            SELECT p.slug, i.name, i.thumb, p.datetime, p.volume, p.median, p.moving_avg,
                   coalesce(s.spark, []::DOUBLE[]) AS spark
            FROM price_history p
            JOIN latest l ON p.slug = l.slug AND p.datetime = l.d
            LEFT JOIN spark s ON s.slug = p.slug
            LEFT JOIN items i ON i.slug = p.slug
            ORDER BY p.volume DESC
            LIMIT ?
            """,
            [spark_days, limit],
        )

    def opportunity_inputs(self, baseline_days: int = 7) -> list[dict]:
        """Per-item inputs for opportunity scoring: latest live order book joined to a
        recent price baseline. Only items that have *both* a snapshot and price history
        appear (you can't judge cheapness without a baseline)."""
        return self._rows(
            """
            WITH max_dt AS (SELECT max(datetime) AS d FROM price_history),
            latest_os AS (
                SELECT * FROM order_snapshots
                QUALIFY row_number() OVER (PARTITION BY slug ORDER BY captured_at DESC) = 1
            ),
            ph_recent AS (
                SELECT
                    slug,
                    avg(volume) AS recent_volume,
                    median(median) AS baseline_median,
                    last(moving_avg ORDER BY datetime) AS baseline_moving_avg,
                    list(closed_price ORDER BY datetime) AS spark
                FROM price_history, max_dt
                WHERE datetime >= max_dt.d - (? * INTERVAL 1 DAY)
                GROUP BY slug
            )
            SELECT
                os.slug, i.name, i.thumb, os.sell_min, os.sell_median, os.buy_max, os.spread,
                os.n_sell_live, os.n_buy_live,
                ph.recent_volume, ph.baseline_median, ph.baseline_moving_avg, ph.spark
            FROM latest_os os
            JOIN ph_recent ph ON os.slug = ph.slug
            LEFT JOIN items i ON i.slug = os.slug
            """,
            [baseline_days],
        )

    # --- rivens ------------------------------------------------------------------

    def upsert_riven_attributes(
        self, attrs: list[RivenAttribute], now: datetime | None = None
    ) -> int:
        now = now or _utcnow()
        rows = [
            (a.id, a.slug, a.group, a.prefix, a.suffix, a.name, now) for a in attrs
        ]
        self.con.executemany(
            """
            INSERT INTO riven_attributes (id, slug, attr_group, prefix, suffix, name, last_seen)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                slug = excluded.slug,
                attr_group = excluded.attr_group,
                prefix = excluded.prefix,
                suffix = excluded.suffix,
                name = excluded.name,
                last_seen = excluded.last_seen
            """,
            rows,
        )
        return len(rows)

    def record_riven_auctions(
        self, weapon_slug: str, auctions: list[RivenAuction], now: datetime | None = None
    ) -> int:
        now = now or _utcnow()
        rows = [
            (
                a.id, now, weapon_slug, a.starting_price, a.buyout_price, a.top_bid,
                a.is_direct_sell, a.re_rolls, a.mod_rank, a.mastery_level, a.polarity,
                a.owner_status, a.owner_reputation, a.visible, a.closed,
                json.dumps([s.model_dump() for s in a.attributes]),
            )
            for a in auctions
        ]
        if rows:
            self.con.executemany(
                """
                INSERT INTO riven_auctions (
                    auction_id, captured_at, weapon_slug, starting_price, buyout_price, top_bid,
                    is_direct_sell, re_rolls, mod_rank, mastery_level, polarity,
                    owner_status, owner_reputation, visible, closed, attributes_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (auction_id, captured_at) DO NOTHING
                """,
                rows,
            )
        return len(rows)

    def riven_demand_proxies(self) -> dict[str, dict]:
        """Per-weapon current riven demand: live auction count and median buyout price.

        Computed from the latest snapshot of each auction, counting only visible, open
        listings. Used as a usage proxy by the disposition predictor.
        """
        rows = self._rows(
            """
            WITH latest AS (
                SELECT * FROM riven_auctions
                QUALIFY row_number() OVER (PARTITION BY auction_id ORDER BY captured_at DESC) = 1
            )
            SELECT
                weapon_slug,
                count(*) FILTER (WHERE visible AND NOT closed) AS n_auctions,
                median(buyout_price) FILTER (WHERE visible AND NOT closed) AS median_price
            FROM latest
            GROUP BY weapon_slug
            """
        )
        return {
            r["weapon_slug"]: {"n_auctions": r["n_auctions"], "median_price": r["median_price"]}
            for r in rows
        }

    def disposition_forecast_inputs(self) -> list[dict]:
        """Assemble everything the disposition predictor needs, one row per weapon.

        Each row: ``{slug, name, disposition (latest), history, n_auctions, median_price}``.
        Weapons with no recorded disposition are skipped. Demand fields are None when no
        auctions have been archived for that weapon yet (the predictor degrades gracefully).
        """
        histories = self.all_disposition_histories()
        names = self.riven_weapon_names()
        demand = self.riven_demand_proxies()
        rows: list[dict] = []
        for slug, hist in histories.items():
            disp_vals = [h["disposition"] for h in hist if h["disposition"] is not None]
            if not disp_vals:
                continue
            d = demand.get(slug, {})
            rows.append(
                {
                    "slug": slug,
                    "name": names.get(slug),
                    "disposition": disp_vals[-1],
                    "history": hist,
                    "n_auctions": d.get("n_auctions"),
                    "median_price": d.get("median_price"),
                }
            )
        return rows

    def weapons_with_auctions(self) -> list[str]:
        return [r["weapon_slug"] for r in self._rows(
            "SELECT DISTINCT weapon_slug FROM riven_auctions ORDER BY weapon_slug"
        )]

    @staticmethod
    def _row_to_auction(r: dict) -> RivenAuction:
        return RivenAuction(
            id=r["auction_id"],
            weapon_url_name=r["weapon_slug"],
            starting_price=r["starting_price"],
            buyout_price=r["buyout_price"],
            top_bid=r["top_bid"],
            is_direct_sell=r["is_direct_sell"],
            visible=r["visible"],
            closed=r["closed"],
            re_rolls=r["re_rolls"] or 0,
            mod_rank=r["mod_rank"] or 0,
            mastery_level=r["mastery_level"],
            polarity=r["polarity"],
            owner_status=r["owner_status"] or "offline",
            owner_reputation=r["owner_reputation"] or 0,
            attributes=[RivenStat(**a) for a in json.loads(r["attributes_json"] or "[]")],
        )

    def latest_riven_auctions(self, weapon_slug: str) -> list[RivenAuction]:
        """Reconstruct each auction's most recent snapshot as a RivenAuction object.

        Returning model objects lets the pure ``rivens`` valuation logic stay the single
        source of truth (no SQL re-implementation of signature/pricing rules)."""
        rows = self._rows(
            """
            SELECT * FROM riven_auctions
            WHERE weapon_slug = ?
            QUALIFY row_number() OVER (PARTITION BY auction_id ORDER BY captured_at DESC) = 1
            """,
            [weapon_slug],
        )
        return [self._row_to_auction(r) for r in rows]

    def all_latest_riven_auctions(self, live_only: bool = True) -> dict[str, list[RivenAuction]]:
        """Every weapon's latest auction snapshots in ONE query, grouped by weapon slug.

        Replaces the N+1 pattern (a window query per weapon). The latest snapshot per auction
        is selected first (QUALIFY), then ``live_only`` keeps exactly the *live* set (visible,
        open, owner online/in-game), the same rows the deal scanner would keep. Filtering
        live *after* the QUALIFY matters: owner_status changes between snapshots, so filtering
        before it could resurface a stale "online" snapshot of an auction whose owner is now
        offline. Pushing the filter into SQL means Python reconstructs far fewer objects.
        """
        # Two fully-static statements (no f-string interpolation), keeps this the only
        # place that could grow into an injection site free of any interpolation pattern.
        rows = self._rows(_RIVEN_AUCTIONS_LIVE_SQL if live_only else _RIVEN_AUCTIONS_ALL_SQL)
        grouped: dict[str, list[RivenAuction]] = {}
        for r in rows:
            grouped.setdefault(r["weapon_slug"], []).append(self._row_to_auction(r))
        return grouped

    # --- catalysts ---------------------------------------------------------------

    def record_void_trader(self, state: VoidTraderState, now: datetime | None = None) -> None:
        now = now or _utcnow()
        self.con.execute(
            """
            INSERT INTO void_trader_snapshots (
                captured_at, character, location, activation, expiry,
                inventory_size, inventory_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (captured_at) DO NOTHING
            """,
            [
                now, state.character, state.location, state.activation, state.expiry,
                len(state.inventory),
                json.dumps([i.model_dump() for i in state.inventory]),
            ],
        )

    def latest_void_trader(self) -> VoidTraderState | None:
        rows = self._rows(
            "SELECT * FROM void_trader_snapshots ORDER BY captured_at DESC LIMIT 1"
        )
        if not rows:
            return None
        r = rows[0]
        return VoidTraderState(
            character=r["character"],
            location=r["location"],
            activation=r["activation"],
            expiry=r["expiry"],
            inventory=json.loads(r["inventory_json"] or "[]"),
        )

    def reversion_backtest_inputs(self, min_days: int = 20) -> list[dict]:
        """Per-item ascending closes + moving-avg lists for the opportunity backtest.

        Only items with at least ``min_days`` of history are returned (a backtest needs a
        run-up). DuckDB's ``list(... ORDER BY ...)`` keeps the series compact (one row/item).
        """
        return self._rows(
            """
            SELECT
                slug,
                list(closed_price ORDER BY datetime) AS closes,
                list(moving_avg ORDER BY datetime) AS mas
            FROM price_history
            GROUP BY slug
            HAVING count(*) >= ?
            """,
            [min_days],
        )

    def disposition_backtest_inputs(self) -> list[dict]:
        """Per-weapon ``{slug, name, history}`` for the disposition backtest harness."""
        names = self.riven_weapon_names()
        return [
            {"slug": slug, "name": names.get(slug), "history": hist}
            for slug, hist in self.all_disposition_histories().items()
        ]

    def record_resurgence(self, state: ResurgenceState, now: datetime | None = None) -> None:
        now = now or _utcnow()
        self.con.execute(
            """
            INSERT INTO resurgence_snapshots (
                captured_at, character, location, activation, expiry,
                inventory_size, inventory_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (captured_at) DO NOTHING
            """,
            [
                now, state.character, state.location, state.activation, state.expiry,
                len(state.inventory),
                json.dumps([i.model_dump() for i in state.inventory]),
            ],
        )

    def latest_resurgence(self) -> ResurgenceState | None:
        rows = self._rows(
            "SELECT * FROM resurgence_snapshots ORDER BY captured_at DESC LIMIT 1"
        )
        if not rows:
            return None
        r = rows[0]
        return ResurgenceState(
            character=r["character"],
            location=r["location"],
            activation=r["activation"],
            expiry=r["expiry"],
            inventory=json.loads(r["inventory_json"] or "[]"),
        )

    def resurgence_price_impact(self) -> list[dict]:
        """For each unvaulted Prime that links to a market set, its price now vs the close
        just before the resurgence window opened, quantifying the dip (and the recovery
        upside once it re-vaults). Only confidently-matched sets appear.
        """
        state = self.latest_resurgence()
        if state is None or state.activation is None:
            return []

        catalog = {
            normalize(r["name"]): r["slug"]
            for r in self._rows(
                "SELECT slug, name FROM items WHERE lower(name) LIKE '%prime set'"
            )
            if r["name"]
        }
        matched = match_resurgence([i.item for i in state.inventory], catalog)
        if not matched:
            return []

        # One query for all matched slugs instead of a per-slug round-trip in the loop.
        slugs = list(set(matched.values()))
        placeholders = ", ".join("?" * len(slugs))
        series_by_slug: dict[str, list[dict]] = {}
        for r in self._rows(
            f"SELECT slug, datetime, closed_price FROM price_history "
            f"WHERE slug IN ({placeholders}) ORDER BY slug, datetime",
            slugs,
        ):
            series_by_slug.setdefault(r["slug"], []).append(r)

        out: list[dict] = []
        for item, slug in matched.items():
            series = series_by_slug.get(slug)
            if not series:
                continue
            price_now = series[-1]["closed_price"]
            before = [s for s in series if s["datetime"] <= state.activation]
            ref = (before[-1] if before else series[0])["closed_price"]
            change = (price_now - ref) / ref if ref else None
            out.append(
                {
                    "item": item,
                    "slug": slug,
                    "price_now": round(price_now, 2) if price_now is not None else None,
                    "price_before": round(ref, 2) if ref is not None else None,
                    "change_since_resurgence": round(change, 4) if change is not None else None,
                }
            )
        out.sort(key=lambda r: (r["change_since_resurgence"] is None, r["change_since_resurgence"]))
        return out

    def all_disposition_histories(self) -> dict[str, list[dict]]:
        """Every weapon's disposition history, grouped by slug (ascending in time)."""
        rows = self._rows(
            "SELECT weapon_slug, captured_at, disposition FROM disposition_history "
            "ORDER BY weapon_slug, captured_at"
        )
        grouped: dict[str, list[dict]] = {}
        for r in rows:
            grouped.setdefault(r["weapon_slug"], []).append(
                {"captured_at": r["captured_at"], "disposition": r["disposition"]}
            )
        return grouped

    # --- alerts (dedup) ----------------------------------------------------------

    def recent_alert_keys(self, within_hours: float, now: datetime | None = None) -> set[str]:
        """Alert keys fired within the window, so a standing signal isn't re-notified."""
        now = now or _utcnow()
        rows = self._rows(
            "SELECT key FROM alert_log WHERE last_alerted_at >= ? - (? * INTERVAL 1 HOUR)",
            [now, within_hours],
        )
        return {r["key"] for r in rows}

    def record_alerts(self, alerts: list, now: datetime | None = None) -> None:
        """Upsert each alert's last-fired time (alerts expose .key/.kind/.title)."""
        now = now or _utcnow()
        rows = [(a.key, a.kind, a.title, now) for a in alerts]
        if rows:
            self.con.executemany(
                """
                INSERT INTO alert_log (key, kind, title, last_alerted_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (key) DO UPDATE SET
                    kind = excluded.kind,
                    title = excluded.title,
                    last_alerted_at = excluded.last_alerted_at
                """,
                rows,
            )

    # --- trade journal -----------------------------------------------------------

    def record_trade(
        self, slug: str, side: str, quantity: int, price: float,
        note: str | None = None, now: datetime | None = None,
    ) -> int:
        now = now or _utcnow()
        row = self.con.execute(
            """
            INSERT INTO trades (slug, side, quantity, price, traded_at, note)
            VALUES (?, ?, ?, ?, ?, ?) RETURNING id
            """,
            [slug, side, quantity, price, now, note],
        ).fetchone()
        return int(row[0])

    def list_trades(self) -> list[dict]:
        return self._rows("SELECT * FROM trades ORDER BY traded_at, id")

    def delete_trade(self, trade_id: int) -> bool:
        before = self.count("trades")
        self.con.execute("DELETE FROM trades WHERE id = ?", [trade_id])
        return self.count("trades") < before


def backup_archive(
    db_path: str | Path, dest_dir: str | Path | None = None, now: datetime | None = None
) -> Path:
    """Copy the archive to a timestamped file and verify the copy opens.

    The DuckDB file is the irreplaceable asset (its history can't be re-fetched), so a
    periodic snapshot is cheap insurance. Run it when ingestion isn't mid-write; the copy
    is integrity-checked by re-opening it read-only before this returns.
    """
    src = Path(db_path)
    if str(db_path) == ":memory:" or not src.exists():
        raise ValueError(f"No archive file to back up at {db_path!r}")

    dest_dir = Path(dest_dir) if dest_dir else src.parent / "backups"
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = (now or _utcnow()).strftime("%Y%m%d-%H%M%S")
    dest = dest_dir / f"{src.stem}-{stamp}{src.suffix}"

    shutil.copy2(src, dest)

    # Integrity check: the copy must open and be queryable.
    con = duckdb.connect(str(dest), read_only=True)
    try:
        con.execute("SELECT count(*) FROM items").fetchone()
    finally:
        con.close()
    return dest
