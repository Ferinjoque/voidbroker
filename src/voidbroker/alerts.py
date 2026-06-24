"""Alert selection, pull the *few* high-conviction, act-now items out of the full signal
set, with stable keys for dedup. Pure functions; the CLI handles persistence + notifying.

The digest shows everything worth a glance; alerts are the subset worth interrupting you for:
a deep undervalue, a strong-roll riven steal, an imminent nerf, a cheap resurged Prime, or a
fat set-arbitrage spread. Each alert carries a stable ``key`` so a standing signal pings once,
not every ingest.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Alert:
    kind: str       # "opportunity" | "riven" | "nerf" | "resurgence" | "arbitrage" | "baro"
    key: str        # stable identity for dedup
    title: str
    detail: str


@dataclass(frozen=True)
class AlertThresholds:
    opp_margin: float = 0.25       # buy >= 25% under baseline
    riven_discount: float = 0.40   # >= 40% below comparable median
    nerf_confidence: float = 0.60  # disposition nerf conviction
    resurgence_dip: float = 0.25   # resurged Prime >= 25% cheaper
    arbitrage_profit: float = 30.0  # set-arbitrage absolute plat profit


_DEFAULT_THRESHOLDS = AlertThresholds()


def select_alerts(
    digest: dict, arbitrage: list[dict] | None = None, *, t: AlertThresholds | None = None
) -> list[Alert]:
    """Extract high-conviction alerts from a digest dict (+ optional arbitrage rows)."""
    t = t or _DEFAULT_THRESHOLDS
    out: list[Alert] = []

    for o in digest.get("opportunities", []):
        if (o.get("margin_pct") or 0) >= t.opp_margin:
            name = o.get("name") or o["slug"]
            out.append(Alert(
                "opportunity", f"opp:{o['slug']}",
                f"Buy {name} @ {o['sell_min']:g}p",
                f"{o['margin_pct']:.0%} under baseline, flips ~{o.get('flip_days_est', 0):g}d",
            ))

    for d in digest.get("riven_deals", []):
        strong = d.get("roll_label") in ("strong", "above avg")
        if strong and (d.get("discount_pct") or 0) >= t.riven_discount:
            name = d.get("weapon_name") or d["weapon_slug"]
            out.append(Alert(
                "riven", f"riven:{d['weapon_slug']}:{d.get('signature', '')}",
                f"{name} riven {d['discount_pct']:.0%} off",
                f"{d['price']:g}p vs {d['comparable_median']:g}p median ({d.get('roll_label')})",
            ))

    for f in digest.get("disposition_forecasts", []):
        if f.get("direction") == "nerf" and (f.get("confidence") or 0) >= t.nerf_confidence:
            name = f.get("name") or f["slug"]
            out.append(Alert(
                "nerf", f"nerf:{f['slug']}",
                f"{name} likely disposition NERF",
                f"disposition {f['current_disposition']:g}, {f['confidence']:.0%} conviction",
            ))

    res = digest.get("resurgence")
    if res:
        for b in res.get("best_buys", []):
            chg = b.get("change_since_resurgence")
            if chg is not None and chg <= -t.resurgence_dip:
                out.append(Alert(
                    "resurgence", f"resurg:{b['slug']}",
                    f"{b['item']} {abs(chg):.0%} cheaper (resurgence)",
                    f"{b['price_now']:g}p now; appreciates after re-vault",
                ))

    for a in arbitrage or []:
        if (a.get("profit") or 0) >= t.arbitrage_profit:
            name = a.get("name") or a["slug"]
            verb = "build" if a.get("direction") == "build" else "split"
            detail = (
                f"{verb}: set {a['set_price']:g}p vs parts {a['parts_cost']:g}p "
                f"({a['margin_pct']:.0%})"
            )
            out.append(Alert(
                "arbitrage", f"arb:{a['slug']}",
                f"{name} set arbitrage +{a['profit']:g}p", detail,
            ))

    baro = digest.get("void_trader")
    if baro and baro.get("phase") == "active":
        out.append(Alert(
            "baro", f"baro:active:{baro.get('hours_until_departure')}",
            "Baro Ki'Teer is here",
            f"leaves in {baro.get('hours_until_departure')}h, {baro.get('inventory_size')} items",
        ))

    return out


def render_markdown(alerts: list[Alert], now: object, new_keys: set[str] | None = None) -> str:
    """A dated alert digest as markdown. ``new_keys`` marks first-time alerts with a ★."""
    new_keys = new_keys or set()
    lines = [f"# voidbroker alerts, {now}", ""]
    if not alerts:
        lines.append("_No high-conviction signals right now._")
        return "\n".join(lines)
    groups: dict[str, list[Alert]] = {}
    for a in alerts:
        groups.setdefault(a.kind, []).append(a)
    titles = {
        "opportunity": "Buy opportunities", "riven": "Riven steals",
        "nerf": "Disposition nerf watch", "resurgence": "Prime Resurgence",
        "arbitrage": "Set arbitrage", "baro": "Baro",
    }
    for kind, items in groups.items():
        lines.append(f"## {titles.get(kind, kind)}")
        for a in items:
            star = "★ " if a.key in new_keys else ""
            lines.append(f"- {star}**{a.title}**, {a.detail}")
        lines.append("")
    return "\n".join(lines)
