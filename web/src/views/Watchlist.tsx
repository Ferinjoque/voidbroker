import { useQuery } from "@tanstack/react-query";
import { api, type PriceBar } from "../lib/api";
import { ItemName, Panel, Pill, Sparkline, StarButton } from "../components/ui";
import { pct, plat } from "../lib/format";
import { useWatchlist } from "../lib/watchlist";

type OpenItem = (slug: string, name?: string | null, thumb?: string | null) => void;

function summarize(series: PriceBar[]) {
  const last = series[series.length - 1];
  const first = series[0];
  const change = (last.closed_price - first.open_price) / (first.open_price || 1);
  return { last: last.closed_price, change, spark: series.map((b) => b.closed_price) };
}

/** One pinned item: self-contained query so the list loads progressively and a single
    failed/empty item doesn't blank the whole board. Click anywhere to open the drawer. */
function WatchRow({ slug, onOpen }: { slug: string; onOpen: OpenItem }) {
  const q = useQuery({ queryKey: ["prices", slug], queryFn: () => api.itemPrices(slug) });
  const thumb = q.data?.thumb ?? null;
  const s = q.data && q.data.series.length > 0 ? summarize(q.data.series) : null;

  return (
    <div
      onClick={() => onOpen(slug, q.data?.name, thumb)}
      className="row-in flex cursor-pointer items-center gap-4 border-t border-void-800/70 px-4 py-3 transition-colors first:border-t-0 hover:bg-void-800/50"
    >
      <StarButton slug={slug} />
      <div className="min-w-0 flex-1">
        <ItemName name={q.data?.name} slug={slug} thumb={thumb} />
      </div>
      {q.isPending ? (
        <span className="text-xs text-ink-700">loading…</span>
      ) : s ? (
        <>
          <Sparkline data={s.spark} />
          <div className="w-20 text-right">
            <div className="nums text-sm text-ink-100">{plat(s.last)}</div>
            <Pill tone={s.change >= 0 ? "up" : "down"}>
              {s.change >= 0 ? "▲" : "▼"} {pct(Math.abs(s.change))}
            </Pill>
          </div>
        </>
      ) : (
        <span className="text-xs text-ink-700">no price history</span>
      )}
    </div>
  );
}

export function Watchlist({ onOpenItem }: { onOpenItem: OpenItem }) {
  const slugs = useWatchlist();

  return (
    <div>
      <header className="mb-6">
        <h1 className="display text-3xl font-semibold tracking-tight text-ink-50">Watchlist</h1>
        <p className="mt-1 max-w-[72ch] text-sm text-ink-400">
          Items you've pinned. Star anything from Markets, the command palette, or an item
          drawer to track its price here. Stored locally; it never leaves this machine.
        </p>
      </header>

      <Panel title="Pinned items" accent="var(--color-gold)" bare={slugs.length === 0}>
        {slugs.length === 0 ? (
          <div className="surface px-5 py-12 text-center text-sm text-ink-400">
            Nothing pinned yet.
            <div className="mt-1.5 text-xs text-ink-600">
              Press <kbd className="nums rounded border border-void-700 px-1.5 py-0.5">⌘K</kbd>,
              find an item, and tap the star to add it.
            </div>
          </div>
        ) : (
          <div className="surface overflow-hidden p-0">
            {slugs.map((slug) => (
              <WatchRow key={slug} slug={slug} onOpen={onOpenItem} />
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
