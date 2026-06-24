import { useState, type CSSProperties } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import { api, wfm, type DispositionForecast } from "../lib/api";
import { AsyncBlock, FilterChip, Meter, Pager, Panel, Pill, type Tone } from "../components/ui";
import { usePagination } from "../hooks/usePagination";

type Filter = "all" | "nerf" | "buff";

const DIR_TONE: Record<string, Tone> = { nerf: "down", buff: "up", stable: "neutral" };

/** Bidirectional gauge: fill grows left from center for nerf pressure (red),
    right for buff pressure (green). Magnitude is |pressure|, capped at the half-width. */
function PressureBar({ pressure }: { pressure: number }) {
  const mag = Math.min(1, Math.abs(pressure)) * 50;
  const buff = pressure > 0;
  const color = pressure === 0 ? "var(--color-ink-600)" : buff ? "var(--color-up)" : "var(--color-down)";
  return (
    <div className="relative h-2 w-full overflow-hidden rounded-full bg-void-800">
      <div className="absolute left-1/2 top-0 h-full w-px -translate-x-1/2 bg-void-600" />
      <div
        className="absolute top-0 h-full transition-[width,left] duration-500 ease-out"
        style={{
          left: buff ? "50%" : `${50 - mag}%`,
          width: `${mag}%`,
          background: color,
          borderRadius: buff ? "0 9999px 9999px 0" : "9999px 0 0 9999px",
        }}
      />
    </div>
  );
}

function Row({ f, i }: { f: DispositionForecast; i: number }) {
  const [open, setOpen] = useState(false);
  const tone = DIR_TONE[f.direction] ?? "neutral";
  return (
    <div className="row-in border-t border-void-800/70 first:border-t-0" style={{ "--i": i } as CSSProperties}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="grid w-full grid-cols-[1fr_auto] items-center gap-x-6 gap-y-3 px-4 py-3.5 text-left transition-colors hover:bg-void-800/40 sm:grid-cols-[minmax(0,1.3fr)_5.5rem_minmax(8rem,1fr)_6rem_auto]"
      >
        {/* Weapon */}
        <div className="min-w-0 leading-tight">
          <div className="truncate font-medium text-ink-100">{f.name ?? f.slug}</div>
          <div className="nums text-[11px] text-ink-700">{f.slug}</div>
        </div>

        {/* Current disposition */}
        <div className="hidden text-right sm:block">
          <div className="nums text-base text-ink-100">{f.current_disposition.toFixed(2)}</div>
          <div className="text-[10px] uppercase tracking-wide text-ink-700">disp</div>
        </div>

        {/* Pressure gauge */}
        <div className="flex items-center gap-3">
          <PressureBar pressure={f.pressure} />
          <span
            className={`nums w-12 shrink-0 text-right text-xs ${
              f.pressure > 0 ? "text-up" : f.pressure < 0 ? "text-down" : "text-ink-600"
            }`}
          >
            {f.pressure > 0 ? "+" : ""}
            {f.pressure.toFixed(2)}
          </span>
        </div>

        {/* Confidence */}
        <div className="hidden w-24 sm:block">
          <div className="mb-1 flex justify-between text-[10px] uppercase tracking-wide text-ink-700">
            <span>conf</span>
            <span className="nums text-ink-400">{Math.round(f.confidence * 100)}%</span>
          </div>
          <Meter
            value={f.confidence}
            color={tone === "down" ? "var(--color-down)" : tone === "up" ? "var(--color-up)" : "var(--color-ink-600)"}
          />
        </div>

        {/* Call + expand chevron */}
        <div className="flex items-center justify-end gap-2.5">
          <Pill tone={tone}>{f.direction}</Pill>
          <ChevronDown
            size={15}
            className={`text-ink-600 transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          />
        </div>
      </button>

      {/* Expanded rationale */}
      <div
        className="grid transition-[grid-template-rows] duration-300 ease-out"
        style={{ gridTemplateRows: open ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden">
          <div className="space-y-2 px-4 pb-4 pl-5">
            {f.reasons.map((r, ri) => (
              <div key={ri} className="flex gap-2.5 text-sm text-ink-300">
                <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-ink-600" />
                <span className="max-w-[80ch]">{r}</span>
              </div>
            ))}
            <div className="flex flex-wrap items-center gap-4 pt-1 text-[11px] text-ink-700">
              <span>
                evidence: {f.n_history} snapshot{f.n_history === 1 ? "" : "s"}
              </span>
              <span>
                demand: {f.demand == null ? "unmeasured" : `${Math.round(f.demand * 100)}%`}
              </span>
              <a
                href={wfm.rivenAuctions(f.slug)}
                target="_blank"
                rel="noreferrer"
                className="text-gold transition-colors hover:text-gold-dim"
              >
                View riven auctions ↗
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ForecastList({ rows, filter }: { rows: DispositionForecast[]; filter: Filter }) {
  const pg = usePagination(rows, 15);
  if (rows.length === 0) {
    return (
      <div className="surface px-5 py-8 text-center text-sm text-ink-400">
        No {filter === "nerf" ? "nerf" : "buff"} candidates in range right now.
      </div>
    );
  }
  return (
    <div>
      <div className="surface overflow-hidden p-0">
        {pg.pageItems.map((f, i) => (
          <Row key={f.slug} f={f} i={i} />
        ))}
      </div>
      <Pager {...pg} onPage={pg.setPage} />
    </div>
  );
}

export function Forecast() {
  const [filter, setFilter] = useState<Filter>("all");
  const q = useQuery({ queryKey: ["disposition-forecast"], queryFn: () => api.dispositionForecast() });

  return (
    <div>
      <header className="mb-6">
        <h1 className="display text-3xl font-semibold tracking-tight text-ink-50">
          Disposition forecast
        </h1>
        <p className="mt-1 max-w-[74ch] text-sm text-ink-400">
          The headline call: which riven dispositions DE is likely to{" "}
          <span className="text-down">nerf</span> or <span className="text-up">buff</span> next,
          read from how far each sits from baseline, current riven demand, and the archived
          trajectory. A heuristic that sharpens as the local history compounds.
        </p>
      </header>

      <Panel
        title="Pressure ranking"
        caption="conviction-ordered · click a row for the reasoning"
        accent="var(--color-violet)"
        actions={
          <div className="flex items-center gap-1">
            <FilterChip active={filter === "all"} onClick={() => setFilter("all")}>
              All
            </FilterChip>
            <FilterChip active={filter === "nerf"} onClick={() => setFilter("nerf")}>
              Nerf risk
            </FilterChip>
            <FilterChip active={filter === "buff"} onClick={() => setFilter("buff")}>
              Buff likely
            </FilterChip>
          </div>
        }
      >
        <AsyncBlock
          query={q}
          empty={(d) => d.forecasts.length === 0}
          skeletonCols={5}
          emptyNode={
            <div className="surface px-5 py-10 text-center text-sm text-ink-400">
              No disposition data yet.
              <div className="mt-1.5 text-xs text-ink-600">
                Run <code className="nums text-ink-100">voidbroker ingest --rivens</code> to capture
                dispositions, then keep <code className="nums text-ink-100">voidbroker schedule</code>{" "}
                running to build the trend.
              </div>
            </div>
          }
        >
          {(d) => (
            <ForecastList
              key={filter}
              rows={d.forecasts.filter((f) => filter === "all" || f.direction === filter)}
              filter={filter}
            />
          )}
        </AsyncBlock>
      </Panel>
    </div>
  );
}
