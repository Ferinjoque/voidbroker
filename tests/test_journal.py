from __future__ import annotations

from voidbroker.journal import compute_journal, summary_to_dict


def _t(slug, side, qty, price):
    return {"slug": slug, "side": side, "quantity": qty, "price": price}


def test_realized_fifo_profit():
    trades = [_t("x", "buy", 10, 50), _t("x", "sell", 4, 80)]
    s = compute_journal(trades)
    assert s.realized_pnl == 120  # 4 * (80-50)
    assert s.n_buys == 1 and s.n_sells == 1
    assert len(s.open_positions) == 1
    pos = s.open_positions[0]
    assert pos.quantity == 6 and pos.avg_cost == 50


def test_fifo_matches_oldest_lots_first():
    trades = [_t("x", "buy", 2, 10), _t("x", "buy", 2, 20), _t("x", "sell", 3, 30)]
    s = compute_journal(trades)
    # sell 3: 2 from the 10-lot (2*20), 1 from the 20-lot (1*10) -> 50
    assert s.realized_pnl == 50
    assert s.open_positions[0].quantity == 1 and s.open_positions[0].avg_cost == 20


def test_unrealized_with_prices():
    trades = [_t("x", "buy", 10, 50)]
    s = compute_journal(trades, prices={"x": 70})
    assert s.unrealized_pnl == 200  # (70-50)*10
    assert s.total_pnl == 200
    assert s.open_positions[0].price == 70


def test_oversell_ignores_excess():
    trades = [_t("x", "buy", 2, 10), _t("x", "sell", 5, 30)]
    s = compute_journal(trades)
    assert s.realized_pnl == 40  # only 2 matched: 2*(30-10)
    assert s.open_positions == []  # nothing left, no negative position


def test_no_prices_leaves_unrealized_none():
    s = compute_journal([_t("x", "buy", 1, 10)])
    assert s.unrealized_pnl is None and s.total_pnl is None
    d = summary_to_dict(s)
    assert d["realized_pnl"] == 0 and d["open_positions"][0]["slug"] == "x"
