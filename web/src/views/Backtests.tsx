import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { api } from "../lib/api";
import { AsyncBlock, Meter, Panel } from "../components/ui";
import { pct as asPct, signedPct as signed } from "../lib/format";

function Stat({ label, value, tone, sub }: { label: string; value: string; tone?: string; sub?: ReactNode }) {
  return (
    <div>
      <div className="text-[10.5px] uppercase tracking-[0.08em] text-ink-600">{label}</div>
      <div className={`display mt-0.5 text-3xl ${tone ?? "text-ink-50"}`}>{value}</div>
      {sub && <div className="mt-0.5 text-xs text-ink-600">{sub}</div>}
    </div>
  );
}

function OpportunityCard() {
  const q = useQuery({ queryKey: ["opp-backtest"], queryFn: api.opportunityBacktest });
  return (
    <Panel title="Buy-the-dip" caption="does sub-baseline price revert?" accent="var(--color-gold)">
      <AsyncBlock query={q} empty={(d) => d.signals === 0} emptyNode={<div className="surface px-5 py-6 text-sm text-ink-400">Not enough price history yet.</div>}>
        {(d) => {
          const edgePos = (d.edge ?? 0) > 0;
          return (
            <div className="surface p-6">
              <div className="flex flex-wrap items-end gap-x-12 gap-y-5">
                <Stat
                  label="Median return"
                  value={signed(d.signal_median_return)}
                  tone={edgePos ? "text-up" : "text-down"}
                  sub={<>holding {d.horizon_days}d after a {asPct(d.dip_pct)}+ dip</>}
                />
                <Stat label="vs any-day" value={signed(d.base_median_return)} tone="text-ink-300" />
                <Stat
                  label="Edge"
                  value={signed(d.edge)}
                  tone={edgePos ? "text-up" : "text-down"}
                  sub="signal minus baseline"
                />
                <Stat label="Hit rate" value={asPct(d.signal_hit_rate)} />
              </div>
              <div className="mt-5 max-w-[60ch]">
                <div className="mb-1 flex justify-between text-xs text-ink-600">
                  <span>Median gap to baseline recovered</span>
                  <span className="nums text-ink-300">{asPct(d.median_gap_closed)}</span>
                </div>
                <Meter value={d.median_gap_closed ?? 0} color="var(--color-gold)" />
              </div>
              <p className="mt-4 max-w-[70ch] text-xs leading-relaxed text-ink-500">
                Across {d.signals.toLocaleString()} dip entries in {d.observations.toLocaleString()}{" "}
                observations. Returns are medians (plat prices are fat-tailed, so means mislead). A
                positive edge means buying below the moving-average baseline beat buying on a random
                day, which is the empirical basis for the opportunity score.
              </p>
            </div>
          );
        }}
      </AsyncBlock>
    </Panel>
  );
}

function DispositionCard() {
  const q = useQuery({ queryKey: ["disp-backtest"], queryFn: api.dispositionBacktest });
  return (
    <Panel title="Disposition predictor" caption="calls vs realized DE changes" accent="var(--color-violet)">
      <AsyncBlock
        query={q}
        empty={(d) => d.total_changes === 0}
        emptyNode={
          <div className="surface px-5 py-6 text-sm text-ink-400">
            No realized disposition changes recorded yet. The harness is ready and scores calls as
            DE rebalances and the archive captures the moves.
          </div>
        }
      >
        {(d) => {
          const edge = (d.hit_rate ?? 0) - (d.base_rate ?? 0);
          return (
            <div className="surface p-6">
              <div className="flex flex-wrap items-end gap-x-12 gap-y-5">
                <Stat label="Hit rate" value={asPct(d.hit_rate)} tone={edge > 0 ? "text-up" : "text-down"} sub={`${d.called} directional calls`} />
                <Stat label="vs base rate" value={asPct(d.base_rate)} tone="text-ink-300" sub="always guess majority" />
                <Stat label="Edge" value={signed(edge)} tone={edge > 0 ? "text-up" : "text-down"} />
              </div>
              <div className="mt-5">
                <div className="mb-2 text-[11px] uppercase tracking-wide text-ink-600">Calibration</div>
                <div className="flex flex-col gap-1.5">
                  {d.calibration.map((b) => (
                    <div key={b.bucket} className="flex items-center gap-3 text-xs">
                      <span className="nums w-16 text-ink-500">{b.bucket}</span>
                      <div className="flex-1">
                        <Meter value={b.hit_rate ?? 0} color="var(--color-violet)" />
                      </div>
                      <span className="nums w-20 text-right text-ink-400">
                        {b.hit_rate == null ? "—" : asPct(b.hit_rate)} ({b.n})
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          );
        }}
      </AsyncBlock>
    </Panel>
  );
}

export function Backtests() {
  return (
    <div>
      <header className="mb-6">
        <h1 className="display text-3xl font-semibold tracking-tight text-ink-50">Validation</h1>
        <p className="mt-1 max-w-[74ch] text-sm text-ink-400">
          Signals are only worth trusting if they would have worked. These replay the archive: did
          buy-the-dip pay, and would the disposition predictor's past calls have been right?
        </p>
      </header>
      <OpportunityCard />
      <DispositionCard />
    </div>
  );
}
