# voidbroker roadmap

> Last updated: 2026-06-22. Living document. The numbered tracks are themes, not a
> strict order; the **Sequencing** section at the end says what to build next and why.
>
> **Shipped:** Track A complete (unattended scheduling, tiered/resumable ingestion, backups,
> `doctor`/`/health/ingest`); the disposition predictor + B1 backtest; B2 opportunity backtest
> (median-robust, validated +16.7% edge on the live archive); C1 Prime Resurgence + price-impact
> linking; D1/D2 roll-quality-aware riven appraisal; E1–E4 (docs, public-repo LICENSE, the
> **digest**, CI); F2 a Validation view; F4 a Cmd/Ctrl+K command palette; and **item thumbnails**
> throughout. Remaining are data-gated: **B3** (data-driven predictor weights) and the disposition
> backtest need a real DE rebalance to land; **C1 re-vault timing** and **C2 Baro-return** need more
> rotation/visit history; **C3 patch catalysts** needs a patch-notes feed. **F1** (disposition
> history chart) waits until dispositions actually move (it's a flat line today).

## Where we are

A complete, well-factored skeleton:

- **Backend**, 15 modules (~2.5k lines), 66 tests green, ruff clean. Ingestion, a
  single-file DuckDB archive (3 time series), four signal layers (opportunities, riven
  deals, disposition moves, Baro), a disposition **predictor** (heuristic v1), an
  APScheduler loop, a FastAPI read API, and a Typer CLI.
- **Frontend**, 7-view React/Vite/Tailwind terminal ("void observatory"), 5 vitest,
  Playwright-verified, 0 console errors.

## The one thing that matters

The moat is **a dataset that compounds**: warframe.market keeps ~90 days and *no*
disposition history, so every day voidbroker runs unattended, its archive becomes more
unique and its predictions get more grounded. Everything below is ranked by how directly
it serves that.

The honest gap today: **the skeleton is far ahead of the data.** The archive is shallow
(handful of order snapshots, ~4 disposition snapshots per weapon, auctions concentrated on
a few weapons). The signals and the predictor are *heuristics that have not yet met enough
reality to be validated.* Until ingestion runs reliably and history accumulates, every
forecast is stuck at v1 confidence and we can't prove any edge is real.

So the spine of the roadmap is: **compound the data → measure the edges → deepen them.**

---

## Track A, Data & compounding (foundation, highest leverage)

Nothing else pays off until the archive grows on its own.

- **A1. Unattended scheduling.** `voidbroker schedule` is a foreground process today. Make
  it survive reboots and run hands-off: a Windows Scheduled Task (and a documented
  `launchd`/`systemd`/`cron` equivalent) that runs `full_ingest` on a cadence, with a
  durable log. This is the single highest-value task in the whole roadmap.
- **A2. Full-coverage ingestion, politely.** `--orders` and `--rivens` have only run on
  small slices. Sweep all ~3.8k items for order books and all ~417 weapons for auctions on
  a rotation that respects the ~3 req/s limit and the 509 concurrency cap (e.g. tier the
  catalog: hot items hourly, the long tail daily). Track per-entity "last ingested" so
  sweeps resume and spread load.
- **A3. Archive durability.** Scheduled DuckDB backups (copy/snapshot the file), a size/row
  dashboard, and a documented restore. The dataset *is* the product; losing it resets the
  moat to zero.
- **A4. Ingestion health.** A `voidbroker doctor` / `/health/ingest` that reports last
  successful run per source, rows added, and rate-limit/error counts, so silent failures
  surface instead of quietly starving the models.

## Track B, Validation & calibration (turn heuristics into measured models)

Once history exists, *prove the edges* instead of asserting them.

- **B1. Disposition backtest harness.** ✓ *Shipped* (`backtest.py`, `voidbroker backtest`,
  `GET /signals/disposition-backtest`). Walk-forward: for every realized change it recomputes
  the forecast from data *as of before* the change and scores the direction call, reporting
  hit-rate vs the naive base rate and a confidence-calibration table. Scores the
  price-independent core (reversion + momentum); demand calibration waits on deep auction
  history. Reads near-empty until DE rebalances are captured, that's expected and honest.
- **B2. Opportunity backtest.** Did flagged opportunities actually revert to baseline, and
  in roughly the predicted flip-time? Use it to recalibrate the `margin% × liquidity ÷
  (1+flip_days)` weights and the liquidity saturation constant against reality.
- **B3. Predictor v2 from evidence.** Replace hand-tuned weights with values fit to B1
  (logistic regression / small gradient-boosted model on: distance-from-nominal, demand
  proxy, momentum, weapon class, time-since-last-change). Keep the pure-function shape and
  the human `reasons[]`; only the weighting becomes data-driven.

## Track C, New predictive edges (event-driven forecasting)

The README promises these; they're differentiated and hard for humans to track.

- **C1. Prime vault lifecycle.** ✓ *v1 shipped.* Archives Varzia's **Prime Resurgence**
  rotation from WFCD's `vaultTrader` feed (`worldstate.fetch_resurgence`,
  `catalysts.resurgence_status`, `resurgence_snapshots` table, `voidbroker resurgence`,
  `GET /catalysts/resurgence`, wired into `ingest --worldstate`). Surfaces which vaulted
  Primes are buyable now and the re-vault countdown, the actionable buy-now-hold window.
  **Price-impact linking shipped** (`vault.py`): conservatively maps Varzia's messy item
  names to market "X Prime Set" slugs (exact normalized match, never guesses), and the
  Resurgence view now shows each matched Prime's plat now vs. its pre-window price (live: the
  current rotation is −10% to −31% cheaper, confirming the thesis). *Next:* predict re-vault
  timing from accumulated rotation history; model the post-revault recovery curve.
- **C2. Baro return model.** We snapshot the void trader; turn it into prediction, next
  arrival window, which items historically return, and how their plat prices move around a
  Baro visit. The archive already has the inputs.
- **C3. Balance-patch catalysts.** Tie disposition moves and price shocks to patch dates
  (WFCD/patch-notes feed) so the predictor knows a rebalance just landed and can reset
  momentum instead of mistaking a step-change for noise.

## Track G, Economy arbitrage *(new edges, shipped)*

- **G1. Set vs. parts arbitrage.** ✓ Ingests per-item detail (`/v2/item` → ducats, setParts)
  and flags Prime sets whose price diverges from the summed part prices, "build" (buy parts,
  sell the set) or "split" (buy the set, relist parts). Liquidity-gated prices + a margin/
  profit sanity floor keep stale-price noise out. `voidbroker arbitrage`, `/signals/set-arbitrage`.
- **G2. Ducat efficiency.** ✓ Ranks items by ducats-per-platinum, the cheapest way to convert
  plat into Baro ducats. `voidbroker ducats`, `/signals/ducats`.

## Track D, Riven fair-value depth

The current scanner groups by attribute *signature* only and ignores roll magnitudes.

- **D1. Roll-value-aware appraisal.** Use the actual stat values (and curve/grade per
  weapon) so a god-roll isn't lumped with a weak roll sharing the same positives. Removes
  the documented "some hits are weak rolls" caveat.
- **D2. Riven fair-value model.** Regress buyout price on (weapon disposition, attribute
  set, roll grades, re-rolls, mastery, polarity) to produce a true expected price and a
  residual-based "undervalued" score, replacing the comparable-median heuristic.

## Track E, Product, ops & distribution

Make it the replicable public project the README promises.

- **E1. Docs truth-up.** README still says ML prediction is "the next frontier" and omits
  `/signals/disposition-forecast` + the `forecast` CLI. Refresh README + API table + add a
  Forecast section. (Quick win, do alongside the next feature.)
- **E2. Public-repo readiness.** License, a clean `uv sync` + `npm install` quickstart
  verified from scratch, screenshots/GIFs of the terminal, a small seed/sample archive so a
  cloner sees signals immediately without waiting days for ingestion.
- **E3. Alerts / digest.** When a high-conviction signal lands (deep-undervalued riven,
  imminent high-confidence nerf, Baro arrival), emit a digest, a `voidbroker digest` CLI
  and a frontend badge/feed. This is what makes a compounding archive *actionable*.
- **E4. CI.** GitHub Actions running pytest + ruff + the web build on push, so the public
  repo stays green.

## Track F, Frontend depth

- **F1. Forecast detail.** Click a weapon → disposition history chart with the predicted
  next move and the demand proxy over time. Makes the prediction legible.
- **F2. Backtest visualizations.** Surface B1/B2 results: a hit-rate panel, calibration
  curve, "calls that came true" feed. This is how the terminal earns trust.
- **F3. Opportunities depth.** The view is data-starved until A2; once order books are
  broad, add order-book depth visualization and flip-time context to the drawer.
- **F4. Global polish.** Command palette (jump to any item/weapon), keyboard nav, density
  toggle, shareable deep links per item.

---

## Sequencing (what to build next)

The dependency chain is real: **B and C need A; F2 needs B.** Recommended order:

1. **A1 + A2 + A4**, get unattended, full-coverage ingestion running with health
   visibility. Start the clock on the moat. (Also unblocks the Opportunities view, which is
   empty without broad order books.)
2. **E1**, truth-up the docs while the data accumulates (cheap, keeps the repo honest).
3. **B1**, the disposition backtest, as soon as there are a few realized changes to score.
   This tells us whether the headline feature actually works.
4. **C1 or C2**, the next net-new edge (Prime vault is the higher-impact, Baro the lower-
   risk since we already snapshot it).
5. **B3 / D / F2**, deepen and visualize once there's measured signal to build on.

### Immediate next sprint (proposed)

- A1: Windows Scheduled Task + cross-platform docs for `schedule`, with rotating logs.
- A2: tiered, resumable full-coverage ingestion (last-ingested tracking + a rotation plan).
- A4: `voidbroker doctor` + `/health/ingest`.
- E1: README/API-doc refresh for the predictor (folded in, low cost).

That ends with the archive compounding on its own and visibly healthy, the precondition
for everything else, plus honest docs.
