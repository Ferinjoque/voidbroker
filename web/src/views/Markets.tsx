import { lazy, Suspense, useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type PriceBar } from "../lib/api";
import { Pill, SkeletonRows, StarButton, Thumb } from "../components/ui";
import { useItemSearch } from "../hooks/useItemSearch";
import { pct, plat } from "../lib/format";

// The chart library is heavy and only this view + the drawer use it, so it's code-split.
const PriceChart = lazy(() =>
  import("../components/PriceChart").then((m) => ({ default: m.PriceChart })),
);

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div>
      <div className="text-[10.5px] uppercase tracking-[0.08em] text-ink-600">{label}</div>
      <div className={`display mt-0.5 text-xl ${tone ?? "text-ink-50"}`}>{value}</div>
    </div>
  );
}

function summarize(series: PriceBar[]) {
  const first = series[0];
  const last = series[series.length - 1];
  const change = (last.closed_price - first.open_price) / (first.open_price || 1);
  return {
    last: last.closed_price,
    change,
    hi: Math.max(...series.map((b) => b.max_price)),
    lo: Math.min(...series.map((b) => b.min_price)),
    vol: series.reduce((s, b) => s + b.volume, 0),
  };
}

export function Markets({ slug, onSlugChange }: { slug: string; onSlugChange: (s: string) => void }) {
  const top = useQuery({ queryKey: ["volume-top"], queryFn: () => api.volumeLeaderboard(1) });
  const effective = slug || top.data?.items[0]?.slug || "";

  const [open, setOpen] = useState(false);
  const { query: draft, setQuery: setDraft, debounced, results } = useItemSearch(open);
  useEffect(() => {
    if (!slug && effective) setDraft(effective);
  }, [slug, effective, setDraft]);

  const choose = (s: string) => {
    onSlugChange(s);
    setDraft(s);
    setOpen(false);
  };

  const q = useQuery({
    queryKey: ["prices", effective],
    queryFn: () => api.itemPrices(effective),
    enabled: !!effective,
  });

  const stats = q.data && q.data.series.length ? summarize(q.data.series) : null;

  return (
    <div>
      <header className="mb-6">
        <h1 className="display text-3xl font-semibold tracking-tight text-ink-50">Markets</h1>
        <p className="mt-1 text-sm text-ink-400">Daily candlesticks from the price archive.</p>
      </header>

      <form
        className="relative mb-5 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (results.length) choose(results[0].slug);
          else onSlugChange(draft.trim());
          setOpen(false);
        }}
      >
        <div className="relative w-96">
          <input
            value={draft}
            onChange={(e) => {
              setDraft(e.target.value);
              setOpen(true);
            }}
            onFocus={() => setOpen(true)}
            onBlur={() => setTimeout(() => setOpen(false), 150)}
            spellCheck={false}
            placeholder="Search by name, e.g. mirage prime"
            className="w-full rounded-[0.6rem] border border-void-700 bg-void-850/70 px-3.5 py-2.5 text-sm text-ink-100 outline-none transition-colors focus:border-gold"
          />
          {open && debounced.length >= 2 && results.length > 0 && (
            <ul className="fade-in absolute z-20 mt-1.5 max-h-80 w-[150%] overflow-auto rounded-[0.6rem] border border-void-700 bg-void-850 p-1.5 shadow-2xl">
              {results.map((r) => (
                <li key={r.slug}>
                  <button
                    type="button"
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => choose(r.slug)}
                    className="flex w-full items-center gap-3 rounded-md px-2.5 py-1.5 text-left transition-colors hover:bg-void-800"
                  >
                    <Thumb thumb={r.thumb} size={26} />
                    <span className="flex-1 text-sm text-ink-100">{r.name ?? r.slug}</span>
                    <span className="nums text-[11px] text-ink-700">{r.slug}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <button
          type="submit"
          aria-label="Load item"
          className="grid h-[42px] w-[42px] place-items-center rounded-[0.6rem] border border-void-700 bg-void-800 text-ink-300 transition-colors hover:border-gold hover:text-gold"
        >
          →
        </button>
      </form>

      <div className="surface p-5">
        {(q.isPending || (!effective && top.isPending)) && <SkeletonRows rows={8} cols={1} />}
        {q.isError && (
          <div className="px-3 py-12 text-center text-sm text-ink-400">
            No price history for <span className="nums text-ink-100">{effective}</span>. Try a slug
            from the dashboard, or ingest more items.
          </div>
        )}
        {q.data && q.data.series.length > 0 && stats && (
          <>
            <div className="mb-5 flex flex-wrap items-end gap-x-10 gap-y-4">
              <div className="flex items-center gap-3">
                <Thumb thumb={q.data.thumb} size={40} />
                <div>
                  <div className="flex items-center gap-2.5">
                    <span className="display text-lg font-medium text-ink-100">
                      {q.data.name ?? effective}
                    </span>
                    <Pill tone={stats.change >= 0 ? "up" : "down"}>
                      {stats.change >= 0 ? "▲" : "▼"} {pct(Math.abs(stats.change))}
                    </Pill>
                    <StarButton slug={effective} size={16} />
                  </div>
                  <div className="nums text-[11px] text-ink-700">
                    {effective} · last {q.data.series.length}d
                  </div>
                </div>
              </div>
              <Stat label="Last" value={plat(stats.last)} />
              <Stat label="High" value={plat(stats.hi)} tone="text-up" />
              <Stat label="Low" value={plat(stats.lo)} tone="text-down" />
              <Stat label="Volume" value={stats.vol.toLocaleString()} />
            </div>
            <Suspense fallback={<SkeletonRows rows={6} cols={1} />}>
              <PriceChart bars={q.data.series} />
            </Suspense>
          </>
        )}
        {q.data && q.data.series.length === 0 && (
          <div className="px-3 py-12 text-center text-sm text-ink-400">No bars.</div>
        )}
      </div>
    </div>
  );
}
