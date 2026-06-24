# Operations — running the archive unattended

The whole thesis of voidbroker is a dataset that **compounds**. That only happens if
ingestion runs on a cadence without you babysitting it. This is how.

## How ingestion stays bounded and resumable

Every per-item fetch is stamped in a `fetch_state` table (`source`, `ref`, `last_fetch`,
`ok`, `error`). A run with `--batch N` processes only the **stalest N refs per source**
(never-fetched first, then oldest), so:

- each run is bounded and polite (no re-fetching fresh data, respects the ~3 req/s limit);
- coverage rotates through the whole catalog over successive runs;
- a crash mid-sweep just means those refs stay "stale" and get picked up next run.

Disposition is captured for **every** weapon on every run (it rides the single catalog
call), so the predictor's core time series never goes stale regardless of batch size.

Check coverage and freshness any time:

```bash
uv run voidbroker doctor          # table: per-source coverage %, errors, oldest/newest fetch
# or over HTTP while `serve` is running:
curl http://127.0.0.1:8000/health/ingest
```

## Sizing the batch

The catalog is ~3,834 items and ~417 weapons. Pick `batch × runs-per-day` to cover items
roughly daily:

| Cadence | Batch | Items swept/day | Full item sweep |
|---------|-------|-----------------|-----------------|
| 6 h (4×/day) | 400 | 1,600 | ~2.4 days |
| 6 h | 1000 | 4,000 | ~daily |
| 12 h (2×/day) | 1000 | 2,000 | ~2 days |

**Riven auctions are the heavy outlier.** Measured: ~7 s per weapon and ~300+ rows each
(a 187-weapon sweep wrote ~64k auction rows and took ~21 min). Prices and orders are far
cheaper (a 250-item orders sweep finished in ~2 min). So auctions get their **own smaller**
batch via `--auction-batch` (default 40), keeping a scheduled run to a few minutes while
still rotating through all 417 weapons over a day or two. Don't crank `--auction-batch`;
raise `--batch` (prices/orders) instead if you want faster item coverage.

## Windows (Scheduled Task) — recommended

A repeating **one-shot** task is more robust than a long-lived `schedule` process: it
survives reboots and each run is isolated.

```powershell
# Register: bounded ingest every 6h, 400 stalest refs per source, 40 weapons for auctions.
powershell -ExecutionPolicy Bypass -File scripts/install-schedule.ps1 -IntervalHours 6 -Batch 400 -AuctionBatch 40

schtasks /Run   /TN voidbroker-ingest                 # kick one run now
schtasks /Query /TN voidbroker-ingest /V /FO LIST     # inspect

# Remove it (archive untouched):
powershell -ExecutionPolicy Bypass -File scripts/uninstall-schedule.ps1
```

The installer uses `schtasks.exe`, which registers a current-user task without elevation on
most machines. (The PowerShell `Register-ScheduledTask` cmdlet talks to Task Scheduler over
WMI and is often blocked by ACLs in a non-admin session with `HRESULT 0x80070005` — that's
why this avoids it.) If `schtasks` itself is denied, run the script from an elevated
PowerShell, or just run the generated `scripts\scheduled-ingest.cmd` directly / point Task
Scheduler's GUI at it.

App logs rotate at `data/logs/voidbroker.log` (5 × 2 MB); the task's console output appends
to `data/logs/scheduled.log`.

## macOS / Linux (cron)

```cron
# Every 6 hours: bounded, resumable ingest. Adjust the path to your checkout.
0 */6 * * * cd /path/to/voidbroker && /usr/local/bin/uv run voidbroker ingest --batch 400 --auction-batch 40 --orders --rivens --worldstate >> data/logs/cron.log 2>&1
```

### Linux (systemd timer) — alternative

`~/.config/systemd/user/voidbroker.service`:

```ini
[Service]
Type=oneshot
WorkingDirectory=%h/voidbroker
ExecStart=/usr/local/bin/uv run voidbroker ingest --batch 400 --auction-batch 40 --orders --rivens --worldstate
```

`~/.config/systemd/user/voidbroker.timer`:

```ini
[Timer]
OnBootSec=2min
OnUnitActiveSec=6h
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemctl --user enable --now voidbroker.timer
```

## Foreground alternative

If you'd rather keep a live process (e.g. while developing), the built-in scheduler still
works and uses the same tiered batching:

```bash
uv run voidbroker schedule --interval-hours 6 --batch 400 --auction-batch 40   # Ctrl+C to stop
```

## Protect the archive (it *is* the product)

The DuckDB file at `data/voidbroker.duckdb` is the irreplaceable asset — its history can't
be re-fetched. Back it up periodically (a plain file copy while no ingest is mid-write is
fine):

```bash
cp data/voidbroker.duckdb "backups/voidbroker-$(date +%Y%m%d).duckdb"
```

A dedicated `voidbroker backup` command and a scheduled copy are tracked as **A3** in
[ROADMAP.md](ROADMAP.md).
