import { useQuery } from "@tanstack/react-query";
import { api, type Summary, type VolumeRow } from "../lib/api";
import {
  AsyncBlock,
  DataTable,
  ItemName,
  Meter,
  Panel,
  Sparkline,
  type Column,
} from "../components/ui";
import { plat } from "../lib/format";

function Vitals() {
  const q = useQuery({ queryKey: ["summary"], queryFn: api.summary });
  const groups: { label: string; key: keyof Summary; accent: string }[] = [
    { label: "Items", key: "items", accent: "var(--color-cyan)" },
    { label: "Price rows", key: "price_rows", accent: "var(--color-gold)" },
    { label: "Disposition", key: "disposition_rows", accent: "var(--color-violet)" },
    { label: "Order snaps", key: "order_snapshots", accent: "var(--color-up)" },
    { label: "Riven auctions", key: "riven_auctions", accent: "var(--color-violet)" },
    { label: "Baro snaps", key: "void_trader_snapshots", accent: "var(--color-amber)" },
  ];
  return (
    <div className="surface mb-7 flex flex-wrap items-center gap-y-4 px-2 py-4">
      {q.isError && (
        <span className="px-4 text-sm text-down">API offline. Start it with voidbroker serve.</span>
      )}
      {(q.data ? groups : []).map((g, i) => (
        <div
          key={g.label}
          className={`px-5 ${i ? "border-l border-void-800" : ""}`}
        >
          <div className="flex items-center gap-1.5 text-[10.5px] uppercase tracking-[0.08em] text-ink-600">
            <span className="h-1 w-1 rounded-full" style={{ background: g.accent }} />
            {g.label}
          </div>
          <div className="display mt-1 text-2xl text-ink-50">
            {q.data![g.key].toLocaleString()}
          </div>
        </div>
      ))}
      {q.isPending && <span className="px-4 text-sm text-ink-600">Loading archive…</span>}
    </div>
  );
}

export function Dashboard({
  onOpenItem,
}: {
  onOpenItem: (slug: string, name?: string | null, thumb?: string | null) => void;
}) {
  const q = useQuery({ queryKey: ["volume"], queryFn: () => api.volumeLeaderboard(25) });

  return (
    <div>
      <header className="mb-6">
        <h1 className="display text-3xl font-semibold tracking-tight text-ink-50">Market Pulse</h1>
        <p className="mt-1 text-sm text-ink-400">
          Live read of the local archive. The most-traded items, where the liquidity is.
        </p>
      </header>

      <Vitals />

      <Panel title="Most traded" caption="by latest-day volume, click any row for detail">
        <AsyncBlock query={q} empty={(d) => d.items.length === 0} skeletonCols={5}>
          {(d) => {
            const maxVol = Math.max(...d.items.map((r) => r.volume), 1);
            const columns: Column<VolumeRow>[] = [
              {
                key: "slug",
                header: "Item",
                render: (r) => <ItemName name={r.name} slug={r.slug} thumb={r.thumb} />,
              },
              {
                key: "trend",
                header: "14d trend",
                width: "120px",
                render: (r) => <Sparkline data={r.spark} />,
              },
              {
                key: "vol",
                header: "Volume / day",
                align: "right",
                width: "180px",
                render: (r) => (
                  <div className="flex items-center justify-end gap-3">
                    <div className="w-24">
                      <Meter value={r.volume / maxVol} color="var(--color-cyan)" />
                    </div>
                    <span className="w-12 text-right text-ink-100">
                      {r.volume.toLocaleString()}
                    </span>
                  </div>
                ),
              },
              { key: "median", header: "Median", align: "right", render: (r) => plat(r.median) },
              {
                key: "ma",
                header: "Moving avg",
                align: "right",
                render: (r) => <span className="text-ink-400">{plat(r.moving_avg)}</span>,
              },
            ];
            return (
              <DataTable
                columns={columns}
                rows={d.items}
                rowKey={(r) => r.slug}
                onRowClick={(r) => onOpenItem(r.slug, r.name, r.thumb)}
              />
            );
          }}
        </AsyncBlock>
      </Panel>
    </div>
  );
}
