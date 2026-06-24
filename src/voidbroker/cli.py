"""Command-line entrypoint: ``voidbroker ingest`` / ``serve`` / ``info``."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .alerts import render_markdown, select_alerts
from .arbitrage import rank_ducat_efficiency, set_arbitrage
from .backtest import backtest_disposition, backtest_reversion
from .catalysts import resurgence_status, void_trader_status
from .client import WarframeMarketClient
from .config import get_settings
from .digest import build_digest
from .ingest import (
    ingest_item_details,
    ingest_riven_auctions,
    ingest_statistics,
    snapshot_orders,
    sync_catalog,
    sync_resurgence,
    sync_riven_attributes,
    sync_void_trader,
)
from .journal import compute_journal
from .predict import rank_forecasts
from .rivens import find_undervalued
from .signals import rank_opportunities
from .storage import Storage, backup_archive


def _force_utf8_console() -> None:
    """Windows consoles default to cp1252 and crash on rich's Unicode glyphs / dashes."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass


_force_utf8_console()


def _setup_file_logging(db_path: str) -> Path | None:
    """Send the voidbroker loggers to a rotating file beside the archive.

    Unattended (Scheduled Task / cron) runs have nowhere for stdout to go; this captures
    every stage line and per-ref warning so failures are diagnosable after the fact.
    """
    if db_path == ":memory:":
        return None
    log_dir = Path(db_path).parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "voidbroker.log"
    root = logging.getLogger("voidbroker")
    root.setLevel(logging.INFO)
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        handler = RotatingFileHandler(
            log_path, maxBytes=2_000_000, backupCount=5, encoding="utf-8"
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root.addHandler(handler)
    return log_path


app = typer.Typer(help="A local-first quant terminal for the Warframe Market economy.")
console = Console()


def _notify_desktop(title: str, body: str) -> None:
    """Best-effort desktop toast on Windows (balloon via built-in NotifyIcon). Never raises.

    The notification text (which includes external catalog item names) is passed to PowerShell
    out-of-band via environment variables, and the script itself is a fixed, base64-encoded
    payload. No user-controlled data is ever interpolated into the command string, so there is
    no shell/PowerShell injection surface regardless of what an item name contains.
    """
    if sys.platform != "win32":
        return
    import base64
    import os
    import subprocess

    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "$n=New-Object System.Windows.Forms.NotifyIcon;"
        "$n.Icon=[System.Drawing.SystemIcons]::Information;$n.Visible=$true;"
        "$n.ShowBalloonTip(8000,$env:VB_TITLE,$env:VB_BODY,'Info');"
        "Start-Sleep -Seconds 6;$n.Dispose()"
    )
    encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    try:
        subprocess.Popen(  # fire-and-forget so the CLI doesn't block on the balloon
            ["powershell", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            env={**os.environ, "VB_TITLE": title[:120], "VB_BODY": body[:256]},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


async def _run_ingest(
    window: str, orders: bool, rivens: bool, worldstate: bool, details: bool,
    limit: int | None, batch: int | None, auction_batch: int | None,
) -> None:
    settings = get_settings()
    _setup_file_logging(settings.db_path)
    storage = Storage(settings.db_path)
    async with WarframeMarketClient(settings) as client:
        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as prog:
            cat_task = prog.add_task("Syncing catalog…", total=None)
            catalog = await sync_catalog(client, storage)
            prog.update(
                cat_task,
                description=f"Catalog: {catalog.items} items, "
                f"{catalog.riven_weapons} riven weapons",
            )

        # Batch mode rotates through the stalest refs; otherwise sweep all (or first N).
        if batch:
            slugs = storage.stalest_refs("prices", batch)
        else:
            slugs = [r["slug"] for r in storage._rows("SELECT slug FROM items ORDER BY slug")]
            if limit:
                slugs = slugs[:limit]

        with Progress(console=console) as prog:
            task = prog.add_task("Ingesting price history", total=len(slugs))
            rows = await ingest_statistics(
                client, storage, slugs, window=window,
                on_progress=lambda d, t: prog.update(task, completed=d),
            )
        console.print(f"[green]Price history:[/green] {rows} candlestick rows written")

        if orders:
            order_slugs = storage.stalest_refs("orders", batch) if batch else slugs
            with Progress(console=console) as prog:
                task = prog.add_task("Snapshotting order books", total=len(order_slugs))
                snaps = await snapshot_orders(
                    client, storage, order_slugs,
                    on_progress=lambda d, t: prog.update(task, completed=d),
                )
            console.print(f"[green]Order snapshots:[/green] {snaps} written")

        if details:
            detail_slugs = storage.stalest_refs("details", batch) if batch else slugs
            with Progress(console=console) as prog:
                task = prog.add_task("Ingesting item details", total=len(detail_slugs))
                n_det = await ingest_item_details(
                    client, storage, detail_slugs,
                    on_progress=lambda d, t: prog.update(task, completed=d),
                )
            console.print(f"[green]Item details:[/green] {n_det} synced (ducats + set parts)")

        if rivens:
            n_attrs = await sync_riven_attributes(client, storage)
            console.print(f"[green]Riven attributes:[/green] {n_attrs} synced")
            a_batch = auction_batch or batch
            if a_batch:
                weapons = storage.stalest_refs("auctions", a_batch)
            else:
                weapons = [
                    r["slug"]
                    for r in storage._rows("SELECT slug FROM riven_weapons ORDER BY slug")
                ]
                if limit:
                    weapons = weapons[:limit]
            with Progress(console=console) as prog:
                task = prog.add_task("Snapshotting riven auctions", total=len(weapons))
                n_auc = await ingest_riven_auctions(
                    client, storage, weapons,
                    on_progress=lambda d, t: prog.update(task, completed=d),
                )
            console.print(f"[green]Riven auctions:[/green] {n_auc} rows written")

        if worldstate:
            await sync_void_trader(storage, platform=settings.platform)
            await sync_resurgence(storage, platform=settings.platform)
            console.print(
                "[green]Worldstate:[/green] void trader + Prime Resurgence snapshots recorded"
            )

    storage.close()


@app.command()
def ingest(
    window: str = typer.Option("90days", help="Statistics window: 90days or 48hours."),
    orders: bool = typer.Option(False, help="Also snapshot live order books (heavier)."),
    rivens: bool = typer.Option(False, help="Also snapshot riven auctions per weapon."),
    worldstate: bool = typer.Option(False, help="Also snapshot Baro / worldstate catalysts."),
    details: bool = typer.Option(
        False, help="Also fetch per-item detail (ducats + set parts) for arbitrage/ducats."
    ),
    limit: int | None = typer.Option(None, help="Only process the first N items (testing)."),
    batch: int | None = typer.Option(
        None, help="Process only the stalest N refs per source (tiered, resumable sweeps)."
    ),
    auction_batch: int | None = typer.Option(
        None, help="Separate (smaller) stalest-N for the heavy riven-auction sweep."
    ),
) -> None:
    """Refresh the catalog and ingest market data into the local archive.

    Use --batch N for unattended/scheduled runs: each run touches the N most-overdue refs
    per source and rotates through the whole catalog over time, instead of re-fetching
    everything. Disposition is captured for every weapon each run regardless. Riven auctions
    are heavy (~seconds each); --auction-batch keeps them smaller than --batch.
    """
    asyncio.run(
        _run_ingest(window, orders, rivens, worldstate, details, limit, batch, auction_batch)
    )


@app.command()
def info() -> None:
    """Show a summary of what's in the local archive."""
    settings = get_settings()
    storage = Storage(settings.db_path)
    table = Table(title=f"voidbroker archive — {settings.db_path}")
    table.add_column("Table")
    table.add_column("Rows", justify="right")
    tables = (
        "items", "item_details", "riven_weapons", "disposition_history", "price_history",
        "order_snapshots", "riven_attributes", "riven_auctions", "void_trader_snapshots",
        "resurgence_snapshots", "fetch_state",
    )
    for name in tables:
        table.add_row(name, f"{storage.count(name):,}")
    console.print(table)
    storage.close()


@app.command()
def digest(per_section: int = typer.Option(5, help="Items per section.")) -> None:
    """One cross-signal briefing: what's worth acting on right now."""
    settings = get_settings()
    storage = Storage(settings.db_path)
    d = build_digest(storage, datetime.now(UTC), per_section=per_section)
    storage.close()

    console.print("[bold gold1]voidbroker digest[/bold gold1]\n")

    opps = d["opportunities"]
    console.print("[bold]Buy opportunities[/bold] (liquidity-adjusted)")
    if opps:
        for o in opps:
            console.print(
                f"  • {o.get('name') or o['slug']}  buy [gold1]{o['sell_min']:g}[/gold1] "
                f"vs {o['baseline']:g}  ([green]{o['margin_pct']:.0%}[/green], "
                f"flip ~{o['flip_days_est']:g}d)"
            )
    else:
        console.print("  [dim]none — run ingest --orders[/dim]")

    deals = d["riven_deals"]
    console.print("\n[bold]Riven deals[/bold] (quality rolls below comps)")
    if deals:
        for x in deals:
            console.print(
                f"  • {x.get('weapon_name') or x['weapon_slug']}  [gold1]{x['price']:g}[/gold1] "
                f"vs {x['comparable_median']:g}  ([green]{x['discount_pct']:.0%}[/green], "
                f"roll {x['roll_label']})"
            )
    else:
        console.print("  [dim]none — run ingest --rivens[/dim]")

    fc = d["disposition_forecasts"]
    console.print("\n[bold]Disposition watch[/bold] (likely next moves)")
    if fc:
        for f in fc:
            tone = "red" if f["direction"] == "nerf" else "green"
            console.print(
                f"  • {f.get('name') or f['slug']}  [{tone}]{f['direction'].upper()}[/{tone}] "
                f"(disp {f['current_disposition']:g}, conf {f['confidence']:.0%})"
            )
    else:
        console.print("  [dim]none[/dim]")

    res = d["resurgence"]
    if res and res["status"]["phase"] == "active":
        days = (res["status"]["hours_until_rotation"] or 0) / 24
        console.print(f"\n[bold]Prime Resurgence[/bold] (re-vaults in {days:.0f}d)")
        for b in res["best_buys"]:
            chg = b.get("change_since_resurgence")
            tag = f"[green]{abs(chg):.0%} cheaper[/green]" if chg and chg < 0 else ""
            console.print(f"  • {b['item']}  [gold1]{b['price_now']:g}[/gold1] {tag}")

    baro = d["void_trader"]
    if baro and baro["phase"] == "active":
        console.print(
            f"\n[bold]Baro[/bold] is here — leaves in {baro['hours_until_departure']}h "
            f"({baro['inventory_size']} items)"
        )


@app.command()
def alert(
    notify: bool = typer.Option(True, help="Fire a desktop notification for new signals."),
    window_hours: float = typer.Option(18.0, help="Don't re-alert a signal within this window."),
) -> None:
    """Surface NEW high-conviction signals: writes a dated alert file + notifies. Run after
    each ingest (the scheduled task does). Standing signals only ping once per window."""
    settings = get_settings()
    storage = Storage(settings.db_path)
    digest = build_digest(storage, datetime.now(UTC), per_section=10)
    arb = [vars(a) for a in set_arbitrage(storage.set_arbitrage_inputs())]
    alerts = select_alerts(digest, arb)

    recent = storage.recent_alert_keys(window_hours)
    new = [a for a in alerts if a.key not in recent]
    now = datetime.now(UTC)
    storage.record_alerts(alerts, now=now)
    storage.close()

    # Write a dated alert file + a stable latest.md.
    if settings.db_path != ":memory:":
        alert_dir = Path(settings.db_path).parent / "alerts"
        alert_dir.mkdir(parents=True, exist_ok=True)
        md = render_markdown(alerts, now.strftime("%Y-%m-%d %H:%M UTC"), {a.key for a in new})
        stamp = now.strftime("%Y%m%d-%H%M")
        (alert_dir / f"alert-{stamp}.md").write_text(md, encoding="utf-8")
        (alert_dir / "latest.md").write_text(md, encoding="utf-8")

    console.print(
        f"[bold]Alerts:[/bold] {len(alerts)} active, [green]{len(new)} new[/green] "
        f"(within {window_hours:g}h window)"
    )
    for a in new[:15]:
        console.print(f"  [gold1]★[/gold1] {a.title} — [dim]{a.detail}[/dim]")
    if new and notify:
        summary = "; ".join(a.title for a in new[:3])
        _notify_desktop("voidbroker", f"{len(new)} new signals: {summary}")


@app.command()
def journal() -> None:
    """Show trade-journal P&L (realized + unrealized) and open positions. Log trades in the UI."""
    settings = get_settings()
    storage = Storage(settings.db_path)
    trades = storage.list_trades()
    s = compute_journal(trades, storage.latest_prices(min_volume=0.0))
    storage.close()
    if not trades:
        console.print("[yellow]No trades logged.[/yellow] Add them in the web Journal view.")
        return

    def p(v):
        return "—" if v is None else f"{'+' if v >= 0 else '-'}{abs(v):g}p"

    console.print(
        f"[bold]P&L[/bold]  realized [bold]{p(s.realized_pnl)}[/bold]  "
        f"unrealized {p(s.unrealized_pnl)}  total {p(s.total_pnl)}  "
        f"[dim]({s.n_trades} trades, {len(s.open_positions)} open)[/dim]"
    )
    if s.open_positions:
        table = Table(title="Open positions")
        table.add_column("Item")
        table.add_column("Qty", justify="right")
        table.add_column("Avg cost", justify="right")
        table.add_column("Market", justify="right")
        table.add_column("Unrealized", justify="right")
        for pos in s.open_positions:
            table.add_row(
                pos.slug, str(pos.quantity), f"{pos.avg_cost:g}",
                "—" if pos.price is None else f"{pos.price:g}", p(pos.unrealized),
            )
        console.print(table)


@app.command()
def arbitrage(
    limit: int = typer.Option(15, help="How many flips to show."),
    min_margin: float = typer.Option(0.10, help="Minimum margin on the side you buy."),
) -> None:
    """Set-vs-parts arbitrage: build a set from cheap parts, or split a cheap set into parts."""
    settings = get_settings()
    storage = Storage(settings.db_path)
    deals = set_arbitrage(storage.set_arbitrage_inputs(), min_margin=min_margin)
    storage.close()
    if not deals:
        console.print(
            "[yellow]No set arbitrage found.[/yellow] Run "
            "[bold]voidbroker ingest --details[/bold] (and prices) first."
        )
        return
    table = Table(title="Set arbitrage")
    table.add_column("Set")
    table.add_column("Do")
    table.add_column("Set @", justify="right")
    table.add_column("Parts @", justify="right")
    table.add_column("Profit", justify="right")
    table.add_column("Margin", justify="right")
    for d in deals[:limit]:
        verb = (
            "[cyan]buy parts→set[/cyan]"
            if d.direction == "build"
            else "[violet]buy set→parts[/violet]"
        )
        table.add_row(
            d.name or d.slug, verb, f"{d.set_price:g}", f"{d.parts_cost:g}",
            f"[green]{d.profit:g}p[/green]", f"{d.margin_pct:.0%}",
        )
    console.print(table)


@app.command()
def ducats(
    limit: int = typer.Option(15, help="How many items to show."),
    min_ducats: int = typer.Option(15, help="Ignore trivial-ducat items."),
) -> None:
    """Rank items by ducats-per-plat — the cheapest way to turn plat into Baro ducats."""
    settings = get_settings()
    storage = Storage(settings.db_path)
    deals = rank_ducat_efficiency(storage.ducat_efficiency_inputs(), min_ducats=min_ducats)
    storage.close()
    if not deals:
        console.print(
            "[yellow]No ducat data.[/yellow] Run [bold]voidbroker ingest --details[/bold] first."
        )
        return
    table = Table(title="Ducat efficiency (ducats per plat)")
    table.add_column("Item")
    table.add_column("Plat", justify="right")
    table.add_column("Ducats", justify="right")
    table.add_column("Ducats/plat", justify="right")
    for d in deals[:limit]:
        table.add_row(
            d.name or d.slug, f"{d.price:g}", str(d.ducats),
            f"[gold1]{d.ducats_per_plat:g}[/gold1]",
        )
    console.print(table)


@app.command()
def signals(
    limit: int = typer.Option(15, help="How many opportunities to show."),
    min_margin_pct: float = typer.Option(0.05, help="Minimum underpricing vs baseline."),
    baseline_days: int = typer.Option(7, help="Lookback window for the price baseline."),
) -> None:
    """Show the top liquidity-adjusted buy opportunities in the archive."""
    settings = get_settings()
    storage = Storage(settings.db_path)
    rows = storage.opportunity_inputs(baseline_days=baseline_days)
    ranked = rank_opportunities(rows, min_margin_pct=min_margin_pct)
    storage.close()

    if not ranked:
        console.print(
            "[yellow]No opportunities yet.[/yellow] Run "
            "[bold]voidbroker ingest --orders[/bold] first to capture live order books."
        )
        return

    table = Table(title="Top opportunities (liquidity-adjusted)")
    table.add_column("Item")
    table.add_column("Buy @", justify="right")
    table.add_column("Baseline", justify="right")
    table.add_column("Margin", justify="right")
    table.add_column("Vol/day", justify="right")
    table.add_column("Flip~d", justify="right")
    table.add_column("Score", justify="right")
    for o in ranked[:limit]:
        table.add_row(
            o.slug, f"{o.sell_min:g}", f"{o.baseline:g}",
            f"{o.margin:g} ({o.margin_pct:.0%})", f"{o.liquidity:g}",
            f"{o.flip_days_est:g}", f"{o.score:.4f}",
        )
    console.print(table)


@app.command()
def deals(
    limit: int = typer.Option(15, help="How many riven deals to show."),
    min_comparables: int = typer.Option(4, help="Min comparable auctions per signature."),
    min_discount: float = typer.Option(0.25, help="Min discount vs comparable median."),
    positives_only: bool = typer.Option(
        False, help="Group comparables by positive stats only (deeper groups)."
    ),
) -> None:
    """Show undervalued riven listings (priced below their comparables)."""
    settings = get_settings()
    storage = Storage(settings.db_path)
    all_deals = []
    for weapon in storage.weapons_with_auctions():
        auctions = storage.latest_riven_auctions(weapon)
        all_deals.extend(
            find_undervalued(
                weapon, auctions, min_comparables=min_comparables,
                min_discount=min_discount, positives_only=positives_only,
            )
        )
    storage.close()
    all_deals.sort(key=lambda d: d.score, reverse=True)

    if not all_deals:
        console.print(
            "[yellow]No riven deals yet.[/yellow] Run "
            "[bold]voidbroker ingest --rivens[/bold] to snapshot auctions first."
        )
        return

    table = Table(title="Undervalued riven listings")
    table.add_column("Weapon")
    table.add_column("Signature", max_width=34)
    table.add_column("Price", justify="right")
    table.add_column("Median", justify="right")
    table.add_column("Discount", justify="right")
    table.add_column("Roll")
    table.add_column("Comps", justify="right")
    roll_tone = {"strong": "green", "above avg": "cyan", "average": "white", "weak": "red"}
    for d in all_deals[:limit]:
        rc = roll_tone.get(d.roll_label, "white")
        table.add_row(
            d.weapon_slug, d.signature, f"{d.price:g}", f"{d.comparable_median:g}",
            f"{d.discount_pct:.0%}", f"[{rc}]{d.roll_label}[/{rc}]", str(d.comparable_count),
        )
    console.print(table)


@app.command()
def forecast(
    limit: int = typer.Option(20, help="How many forecasts to show."),
    direction: str | None = typer.Option(
        None, help="Filter to 'buff' or 'nerf' calls only."
    ),
) -> None:
    """Predict which riven dispositions DE is likely to buff or nerf next."""
    settings = get_settings()
    storage = Storage(settings.db_path)
    rows = storage.disposition_forecast_inputs()
    storage.close()
    forecasts = rank_forecasts(rows, direction=direction)

    if not forecasts:
        console.print(
            "[yellow]No disposition data yet.[/yellow] Run "
            "[bold]voidbroker ingest --rivens[/bold] to capture dispositions first."
        )
        return

    tone = {"nerf": "red", "buff": "green", "stable": "dim"}
    table = Table(title="Disposition forecast (heuristic v1)")
    table.add_column("Weapon")
    table.add_column("Disp", justify="right")
    table.add_column("Call")
    table.add_column("Pressure", justify="right")
    table.add_column("Conf", justify="right")
    table.add_column("Why", max_width=60)
    for f in forecasts[:limit]:
        colour = tone.get(f.direction, "white")
        table.add_row(
            f.name or f.slug,
            f"{f.current_disposition:g}",
            f"[{colour}]{f.direction.upper()}[/{colour}]",
            f"{f.pressure:+.2f}",
            f"{f.confidence:.0%}",
            f.reasons[0] if f.reasons else "",
        )
    console.print(table)


@app.command()
def backtest() -> None:
    """Score the disposition predictor against realized DE changes in the archive."""
    settings = get_settings()
    storage = Storage(settings.db_path)
    rows = storage.disposition_backtest_inputs()
    storage.close()
    report = backtest_disposition(rows)

    if report.total_changes == 0:
        console.print(
            "[yellow]No disposition changes recorded yet.[/yellow] The harness is ready; "
            "it scores calls as DE rebalances and the archive captures the moves.\n"
            "Keep ingestion running ([bold]voidbroker schedule[/bold] or the OS scheduler)."
        )
        return

    hit = report.hit_rate or 0.0
    base = report.base_rate or 0.0
    edge = hit - base
    colour = "green" if edge > 0.02 else "yellow" if edge >= -0.02 else "red"
    console.print(
        f"[bold]Disposition backtest[/bold] — {report.total_changes} realized changes, "
        f"{report.called} directional calls"
    )
    console.print(
        f"Hit rate [bold]{hit:.0%}[/bold] vs naive base rate {base:.0%}  "
        f"[{colour}](edge {edge:+.0%})[/{colour}]"
    )

    table = Table(title="Calibration (is the confidence honest?)")
    table.add_column("Confidence")
    table.add_column("Calls", justify="right")
    table.add_column("Hit rate", justify="right")
    for b in report.calibration:
        hr = "—" if b["hit_rate"] is None else f"{b['hit_rate']:.0%}"
        table.add_row(b["bucket"], str(b["n"]), hr)
    console.print(table)


@app.command()
def backtest_opportunities(
    dip_pct: float = typer.Option(0.08, help="How far below the moving avg counts as a dip."),
    horizon: int = typer.Option(7, help="Days held after buying the dip."),
) -> None:
    """Backtest the buy-the-dip thesis: do sub-baseline prices revert over the archive?"""
    settings = get_settings()
    storage = Storage(settings.db_path)
    rows = storage.reversion_backtest_inputs()
    storage.close()
    r = backtest_reversion(rows, dip_pct=dip_pct, horizon=horizon)

    if r.signals == 0:
        console.print(
            "[yellow]No dip signals in the archive yet.[/yellow] Needs more daily price history."
        )
        return

    edge = r.edge or 0.0
    colour = "green" if edge > 0.005 else "yellow" if edge >= -0.005 else "red"
    console.print(
        f"[bold]Opportunity backtest[/bold] — buy {r.dip_pct:.0%}+ below baseline, "
        f"hold {r.horizon_days}d ({r.signals:,} signals / {r.observations:,} obs)"
    )
    console.print(
        f"Median return [bold]{(r.signal_median_return or 0):+.1%}[/bold] vs any-day "
        f"{(r.base_median_return or 0):+.1%}  [{colour}](edge {edge:+.1%})[/{colour}]"
    )
    console.print(
        f"Hit rate {(r.signal_hit_rate or 0):.0%} · "
        f"median gap to baseline recovered {(r.median_gap_closed or 0):.0%}"
    )


@app.command()
def baro() -> None:
    """Show Baro Ki'Teer's status from the latest worldstate snapshot."""
    settings = get_settings()
    storage = Storage(settings.db_path)
    state = storage.latest_void_trader()
    storage.close()
    if state is None:
        console.print(
            "[yellow]No worldstate snapshot yet.[/yellow] Run "
            "[bold]voidbroker ingest --worldstate[/bold] first."
        )
        return
    status = void_trader_status(state, datetime.now(UTC))
    console.print(f"[bold]{status.character or 'Void Trader'}[/bold] @ {status.location or '?'}")
    if status.phase == "active":
        console.print(
            f"[green]ACTIVE[/green] — leaves in {status.hours_until_departure}h, "
            f"{status.inventory_size} items in stock"
        )
        for i in state.inventory[:30]:
            console.print(f"  • {i.item}  [cyan]{i.ducats}d[/cyan] + {i.credits:,}cr")
    elif status.phase == "incoming":
        console.print(f"[yellow]INCOMING[/yellow] — arrives in {status.hours_until_arrival}h")
    else:
        console.print("[dim]Status unknown[/dim]")


@app.command()
def resurgence() -> None:
    """Show Prime Resurgence (Varzia): vaulted Primes buyable now + when they re-vault."""
    settings = get_settings()
    storage = Storage(settings.db_path)
    state = storage.latest_resurgence()
    storage.close()
    if state is None:
        console.print(
            "[yellow]No resurgence snapshot yet.[/yellow] Run "
            "[bold]voidbroker ingest --worldstate[/bold] first."
        )
        return
    status = resurgence_status(state, datetime.now(UTC))
    console.print(f"[bold]{status.character or 'Varzia'}[/bold] — Prime Resurgence")
    if status.phase == "active":
        days = (status.hours_until_rotation or 0) / 24
        console.print(
            f"[green]ACTIVE[/green] — {status.item_count} Primes unvaulted, window closes in "
            f"{days:.1f}d. Buy now while supply is up; they appreciate after re-vault."
        )
        for i in state.inventory:
            if not i.is_pack:
                console.print(f"  • {i.item}  [cyan]{i.ducats} Aya[/cyan]")
    elif status.phase == "upcoming":
        console.print(f"[yellow]UPCOMING[/yellow] — starts in {status.hours_until_start}h")
    else:
        console.print("[dim]Status unknown[/dim]")


async def _run_scheduler(
    interval_hours: float, orders: bool, rivens: bool, run_now: bool,
    batch: int | None, auction_batch: int | None,
) -> None:
    from .scheduler import build_scheduler, make_ingest_job

    settings = get_settings()
    log_path = _setup_file_logging(settings.db_path)
    if log_path:
        console.print(f"[dim]Logging to {log_path}[/dim]")
    if run_now:
        console.print("Running initial ingest…")
        await make_ingest_job(
            settings, orders=orders, rivens=rivens, batch=batch, auction_batch=auction_batch
        )()

    scheduler = build_scheduler(
        settings, interval_hours=interval_hours, orders=orders, rivens=rivens,
        batch=batch, auction_batch=auction_batch,
    )
    scheduler.start()
    console.print(
        f"[green]Scheduler running[/green] — full ingest every {interval_hours}h. "
        "Press Ctrl+C to stop."
    )
    while True:  # keep the event loop alive for the scheduler
        await asyncio.sleep(3600)


@app.command()
def schedule(
    interval_hours: float = typer.Option(12.0, help="Hours between full ingests."),
    orders: bool = typer.Option(True, help="Include order-book snapshots each run."),
    rivens: bool = typer.Option(True, help="Include riven auction snapshots each run."),
    run_now: bool = typer.Option(True, help="Run one ingest immediately on start."),
    batch: int = typer.Option(
        400, help="Stalest refs per source per run (tiered rotation). 0 = full sweep."
    ),
    auction_batch: int = typer.Option(
        40, help="Stalest weapons for the heavy riven-auction sweep per run."
    ),
) -> None:
    """Run recurring ingestion until interrupted — this is what builds the archive.

    For unattended operation, prefer registering a repeating one-shot ``ingest --batch``
    via the OS scheduler (see scripts/install-schedule.ps1 and docs/OPERATIONS.md); it
    survives reboots without a babysat process.
    """
    try:
        asyncio.run(_run_scheduler(
            interval_hours, orders, rivens, run_now, batch or None, auction_batch or None
        ))
    except (KeyboardInterrupt, SystemExit):
        console.print("Scheduler stopped.")


@app.command()
def backup(
    dest: str | None = typer.Option(None, help="Backup directory (default: data/backups)."),
) -> None:
    """Snapshot the archive file to a timestamped, integrity-checked backup."""
    settings = get_settings()
    try:
        path = backup_archive(settings.db_path, dest)
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    size_mb = path.stat().st_size / 1_000_000
    console.print(f"[green]Backed up[/green] -> {path} ({size_mb:.1f} MB, verified)")


@app.command()
def doctor() -> None:
    """Report ingestion health: per-source catalog coverage, freshness, and error counts."""
    settings = get_settings()
    storage = Storage(settings.db_path)
    health = storage.ingest_health()
    storage.close()

    cat = health["catalog"]
    console.print(
        f"[bold]Archive[/bold] — {cat['items']:,} items, {cat['riven_weapons']:,} riven weapons"
    )
    table = Table(title="Ingestion health")
    table.add_column("Source")
    table.add_column("Coverage", justify="right")
    table.add_column("Tracked", justify="right")
    table.add_column("Errors", justify="right")
    table.add_column("Oldest fetch")
    table.add_column("Newest fetch")
    for source, s in health["sources"].items():
        cov = s["coverage_pct"]
        colour = "green" if cov >= 90 else "yellow" if cov >= 25 else "red"
        oldest = str(s["oldest_fetch"])[:16] if s["oldest_fetch"] else "—"
        newest = str(s["newest_fetch"])[:16] if s["newest_fetch"] else "—"
        errors = str(s["errors"]) if s["errors"] else "[dim]0[/dim]"
        table.add_row(
            source,
            f"[{colour}]{cov:g}% ({s['tracked']}/{s['catalog']})[/{colour}]",
            str(s["tracked"]),
            f"[red]{errors}[/red]" if s["errors"] else errors,
            oldest,
            newest,
        )
    console.print(table)
    if all(s["tracked"] == 0 for s in health["sources"].values()):
        console.print(
            "[yellow]No sweeps recorded yet.[/yellow] Run "
            "[bold]voidbroker ingest --orders --rivens[/bold] to start coverage."
        )


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000),
    reload: bool = typer.Option(False),
) -> None:
    """Run the read API (the frontend terminal connects here)."""
    import uvicorn

    uvicorn.run("voidbroker.api:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
