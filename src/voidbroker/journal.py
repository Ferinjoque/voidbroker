"""Trade journal P&L — pure FIFO accounting over logged buys/sells, no I/O.

Turns the terminal from advisory into accountable: log what you actually bought and sold and
see whether it made plat. Realized profit is computed FIFO (oldest lot sold first) per item;
open lots become positions, valued against the current market price for unrealized P&L.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Position:
    slug: str
    quantity: int
    avg_cost: float
    price: float | None        # current market price, if known
    unrealized: float | None   # (price - avg_cost) * qty


@dataclass(frozen=True)
class JournalSummary:
    realized_pnl: float
    unrealized_pnl: float | None
    total_pnl: float | None
    n_trades: int
    n_buys: int
    n_sells: int
    realized_by_slug: dict[str, float] = field(default_factory=dict)
    open_positions: list[Position] = field(default_factory=list)


def compute_journal(trades: list[dict], prices: dict[str, float] | None = None) -> JournalSummary:
    """FIFO realized P&L + open positions from time-ordered trades.

    Each trade: ``{slug, side ('buy'|'sell'), quantity, price}``, ordered oldest-first. Sells
    are matched against the oldest open buy lots; a sell beyond the held quantity matches what
    it can and ignores the rest (can't be short in-game). ``prices`` (slug→current) values the
    open positions for unrealized P&L.
    """
    lots: dict[str, deque[list[float]]] = defaultdict(deque)  # slug -> deque of [qty, price]
    realized: dict[str, float] = defaultdict(float)
    n_buys = n_sells = 0

    for t in trades:
        slug, side = t["slug"], t["side"]
        qty, price = int(t["quantity"]), float(t["price"])
        if side == "buy":
            n_buys += 1
            lots[slug].append([qty, price])
        elif side == "sell":
            n_sells += 1
            remaining = qty
            queue = lots[slug]
            while remaining > 0 and queue:
                lot = queue[0]
                take = min(remaining, lot[0])
                realized[slug] += take * (price - lot[1])
                lot[0] -= take
                remaining -= take
                if lot[0] <= 0:
                    queue.popleft()

    open_positions: list[Position] = []
    unrealized = 0.0
    have_prices = False
    for slug, queue in lots.items():
        qty = int(sum(lot[0] for lot in queue))
        if qty <= 0:
            continue
        avg = sum(lot[0] * lot[1] for lot in queue) / qty
        cur = prices.get(slug) if prices else None
        unreal = None
        if cur is not None:
            unreal = round((cur - avg) * qty, 2)
            unrealized += unreal
            have_prices = True
        open_positions.append(Position(slug, qty, round(avg, 2), cur, unreal))

    realized_total = round(sum(realized.values()), 2)
    unrealized_total = round(unrealized, 2) if have_prices else None
    total = round(realized_total + unrealized_total, 2) if unrealized_total is not None else None
    open_positions.sort(key=lambda p: (p.unrealized is None, -(p.unrealized or 0)))

    return JournalSummary(
        realized_pnl=realized_total,
        unrealized_pnl=unrealized_total,
        total_pnl=total,
        n_trades=n_buys + n_sells,
        n_buys=n_buys,
        n_sells=n_sells,
        realized_by_slug={k: round(v, 2) for k, v in realized.items() if v},
        open_positions=open_positions,
    )


def summary_to_dict(s: JournalSummary) -> dict:
    return {
        "realized_pnl": s.realized_pnl,
        "unrealized_pnl": s.unrealized_pnl,
        "total_pnl": s.total_pnl,
        "n_trades": s.n_trades,
        "n_buys": s.n_buys,
        "n_sells": s.n_sells,
        "realized_by_slug": s.realized_by_slug,
        "open_positions": [
            {
                "slug": p.slug, "quantity": p.quantity, "avg_cost": p.avg_cost,
                "price": p.price, "unrealized": p.unrealized,
            }
            for p in s.open_positions
        ],
    }
