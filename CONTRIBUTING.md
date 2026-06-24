# Contributing to voidbroker

Thanks for taking a look. voidbroker is a local-first project; everything runs on your
machine with no hosting required.

## Setup

```bash
uv sync                       # Python deps into a local .venv
uv run voidbroker seed        # a small archive so the UI shows data
cd web && npm install         # frontend deps
```

## Project layout

- `src/voidbroker/`: Python backend (ingestion, DuckDB archive, signals, FastAPI, Typer CLI).
- `web/`: React + Vite + Tailwind terminal.
- `tests/`: pytest suite (network mocked, DB in-memory, fully offline).
- `docs/`: API reference, operations guide, roadmap.

## Before opening a PR

Backend:

```bash
uv run pytest                 # all tests must pass
uv run ruff check src tests   # lint must be clean
```

Frontend (from `web/`):

```bash
npx tsc --noEmit              # type-check
npm run lint                  # eslint
npx vitest run                # unit tests
npm run build                 # production build must succeed
```

CI runs all of the above on every push and pull request.

## Conventions

- Conventional commit subjects: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- Keep functions small and files focused; prefer many small modules.
- No em dashes in shipped copy or docs (see `DESIGN.md`); use commas, colons, or periods.
- Frontend follows `DESIGN.md`: semantic color, dense tables over cards, compositor-only
  animation, accessible focus states.
- Be polite to the warframe.market API: stay within the client's rate limit; never remove it.

## Scope

The roadmap (`docs/ROADMAP.md`) tracks direction. Several predictive features are
intentionally on hold until the local archive accumulates enough history to validate them;
please avoid fitting models to thin data. Bug fixes, UI polish, test coverage, and docs are
always welcome.
