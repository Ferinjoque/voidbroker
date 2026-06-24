# voidbroker

[![CI](https://github.com/Ferinjoque/voidbroker/actions/workflows/ci.yml/badge.svg)](https://github.com/Ferinjoque/voidbroker/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Frontend: React + Vite](https://img.shields.io/badge/frontend-React%20%2B%20Vite-61dafb.svg)](web/)
[![Local-first](https://img.shields.io/badge/local--first-no%20account%2C%20no%20cloud-8b5cf6.svg)](#)

A local trading terminal for Warframe's player market. It watches prices, points out the
trades worth making, and quietly keeps a history that [warframe.market](https://warframe.market)
itself throws away after 90 days.

![voidbroker Markets view](docs/screenshots/markets.png)

## What is this?

Warframe is a game with a big player-run economy. Players sell gear to each other for
**platinum** (the game's premium currency) on warframe.market. Prices move all the time, some
items are quietly mispriced, and the best opportunities (a great roll listed for far too
little, a part that's cheaper than the set it builds) are hard to spot by eye across thousands
of items.

voidbroker pulls that market data onto your machine and turns it into clear answers: what's
cheap right now, what's likely to change soon, and what's worth flipping. It runs as a small
web app you open in your browser.

**If you don't play Warframe:** think of it as a tiny single-player Bloomberg terminal for a
video-game economy. Everything runs locally. No account, no login, nothing leaves your computer.

> **Status, honestly.** The price, arbitrage, and ducat signals work today, and the
> "buy-the-dip" signal is backtested on real data (it beat buying on a random day by about
> 17%). The riven *prediction* feature is a transparent first version: it explains its
> reasoning and gets sharper the longer the tool runs and builds up history. See
> [Roadmap](docs/ROADMAP.md) for what's solid and what's still proving itself.

## What it does

Each of these is a screen in the terminal. Jargon is explained the first time it shows up.

- **Markets**: candlestick price history for any tradable item, with volume and a quick read
  on whether it's trending up or down.
- **Opportunities**: items selling below their recent normal price, ranked by `margin ×
  how-liquid-it-is ÷ how-long-it-takes-to-flip`. A fat margin on something nobody buys loses
  to a thinner one that sells in a day.
- **Riven deals**: rivens are randomized weapon mods, so two "the same" rivens can be worth
  wildly different amounts. This scores live listings against comparable ones and flags
  good rolls priced like junk.
- **Forecast**: every weapon has a *disposition*, a balancing multiplier the developers nudge
  up or down based on how much it gets used. That directly moves riven prices. This predicts
  the likely next move and shows its reasoning.
- **Set arbitrage**: a Prime set is just its parts. When the set and the sum of its parts
  drift apart in price, there's a flip: buy the parts and sell the set, or the reverse.
- **Ducats**: the cheapest items to turn platinum into ducats (a second currency you spend on
  Baro Ki'Teer, a traveling vendor who visits every two weeks).
- **Baro & Prime Resurgence**: countdowns and inventories for the game's scheduled vendors,
  plus how much cheaper currently-unvaulted Prime gear is than usual.
- **Journal**: log your actual buys and sells; it tracks realized and unrealized profit.
- **Watchlist, daily digest, and a `Cmd/Ctrl-K` command palette**: pin items, get a one-screen
  briefing of what's worth acting on, and jump anywhere from the keyboard.

## Screenshots

| Buy opportunities | Undervalued rivens |
|---|---|
| ![Opportunities](docs/screenshots/opportunities.png) | ![Riven deals](docs/screenshots/riven-deals.png) |
| **Disposition forecast** | |
| ![Forecast](docs/screenshots/forecast.png) | |

## Quickstart

You'll need [uv](https://docs.astral.sh/uv/) (Python) and Node.js.

```bash
git clone https://github.com/Ferinjoque/voidbroker.git
cd voidbroker

uv sync                       # install the backend into a local .venv
uv run voidbroker seed        # pull a small market slice so every screen has data
uv run voidbroker serve       # start the local API at http://127.0.0.1:8000
```

Then start the web terminal in a second shell:

```bash
cd web
npm install
npm run dev                   # open http://localhost:5173
```

`seed` is a quick one-time populate (about 150 polite API calls) so you can see the terminal
working immediately. To build the full archive and keep it fresh, run ingestion on a schedule.

### Keep it up to date

The longer voidbroker runs, the more history it has, which is exactly what the forecasts need.
Register a recurring background job that fetches a small batch each time and rotates through
the whole catalog:

```powershell
# Windows: a Scheduled Task that ingests every 6 hours. Each run takes a few minutes.
powershell -ExecutionPolicy Bypass -File scripts/install-schedule.ps1 -IntervalHours 6
```

It's polite by design (about 3 requests/second, bounded batches) and stays out of your way.
For macOS/Linux equivalents and a manual foreground option, see
[docs/OPERATIONS.md](docs/OPERATIONS.md). Check on it any time with `uv run voidbroker doctor`.

## How it works

```
warframe.market API  ──▶  ingestion (rate-limited)  ──▶  local DuckDB archive
                                                              │
                                          signals + forecasts │
                                                              ▼
                          React terminal  ◀──  FastAPI read API
```

- **Backend** (Python): a rate-limited client for warframe.market, a single-file
  [DuckDB](https://duckdb.org/) archive that accumulates price, disposition, and auction
  history, the signal and forecasting logic, and a small [FastAPI](https://fastapi.tiangolo.com/)
  read API. There's also a full command-line interface if you prefer the terminal.
- **Frontend** (`web/`): a React + Vite + Tailwind single-page app that reads from the local
  API. Dense tables, inline charts, keyboard-first.

Why local DuckDB? warframe.market only exposes about 90 days of history and keeps no record of
how weapon dispositions change over time. By snapshotting on a schedule, voidbroker slowly
builds a dataset you can't get any other way, which is what makes the predictions possible.

## Command line

Everything in the UI is also a command, handy for quick checks or scripting:

```bash
uv run voidbroker digest      # one briefing: the few things worth acting on now
uv run voidbroker signals     # buy opportunities
uv run voidbroker forecast    # predicted disposition buffs/nerfs
uv run voidbroker deals       # undervalued rivens
uv run voidbroker arbitrage   # set-vs-parts flips
uv run voidbroker info        # what's currently in your archive
```

`uv run voidbroker --help` lists them all.

## Tech

Python 3.11+, DuckDB, httpx, FastAPI, APScheduler, Typer, uv, pytest, ruff on the backend.
React, Vite, TypeScript, Tailwind, TanStack Query, and lightweight-charts on the frontend.
Everything runs locally with no hosting required.

## Contributing

Issues and PRs are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup and the checks
to run before opening a PR. The design system the frontend follows is in [DESIGN.md](DESIGN.md).

## License

[MIT](LICENSE). voidbroker is a fan project and is not affiliated with Digital Extremes or
warframe.market.
