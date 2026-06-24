# voidbroker web

The terminal UI for voidbroker — a Warframe market analytics frontend. Dark, void-themed,
built to feel like a modern trading terminal rather than a fan site.

## Stack

React 19 + Vite + TypeScript + Tailwind v4 + TanStack Query + lightweight-charts.

## Develop

The backend read API must be running first:

```bash
# from the repo root
uv run voidbroker serve          # http://127.0.0.1:8000
```

Then:

```bash
cd web
npm install
npm run dev                      # http://localhost:5173
```

Point at a non-default API with `VITE_API_BASE`:

```bash
VITE_API_BASE=http://127.0.0.1:9000 npm run dev
```

## Build & test

```bash
npm run build                    # tsc + vite production build
npx vitest run                   # unit tests (formatters)
```

## Views

- **Dashboard** — archive status strip + most-traded leaderboard (click a row to chart it)
- **Opportunities** — liquidity-adjusted buy signals
- **Riven Deals** — undervalued listings vs comparables
- **Disposition** — observed riven disposition buffs/nerfs
- **Baro** — void trader status + inventory
- **Markets** — daily candlestick chart for any item slug

## Design

See [`../DESIGN.md`](../DESIGN.md). Restrained palette: void-blue neutrals, Orokin gold for
signal only, green/red for market direction, monospaced tabular figures for all numbers.
