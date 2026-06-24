import { useQuery } from "@tanstack/react-query";
import { api, type DucatDeal } from "../lib/api";
import { AsyncBlock, ItemName, Meter, PaginatedTable, Panel, type Column } from "../components/ui";
import { plat } from "../lib/format";

function Table({ rows }: { rows: DucatDeal[] }) {
  const maxRatio = Math.max(...rows.map((r) => r.ducats_per_plat), 0.0001);
  const columns: Column<DucatDeal>[] = [
    {
      key: "item",
      header: "Item",
      render: (r) => <ItemName name={r.name} slug={r.slug} thumb={r.thumb} />,
    },
    {
      key: "price",
      header: "Plat",
      align: "right",
      render: (r) => <span className="text-gold">{plat(r.price)}</span>,
    },
    {
      key: "ducats",
      header: "Ducats",
      align: "right",
      render: (r) => <span className="text-amber">{r.ducats}</span>,
    },
    {
      key: "ratio",
      header: "Ducats / plat",
      align: "right",
      width: "180px",
      render: (r) => (
        <div className="flex items-center justify-end gap-2.5">
          <div className="w-24">
            <Meter value={r.ducats_per_plat / maxRatio} color="var(--color-amber)" />
          </div>
          <span className="w-10 text-right text-ink-100">{r.ducats_per_plat}</span>
        </div>
      ),
    },
  ];
  return (
    <PaginatedTable
      columns={columns}
      rows={rows}
      rowKey={(r) => r.slug}
      exportName="voidbroker-ducats"
    />
  );
}

export function Ducats() {
  const q = useQuery({ queryKey: ["ducats"], queryFn: api.ducats });
  return (
    <div>
      <header className="mb-6">
        <h1 className="display text-3xl font-semibold tracking-tight text-ink-50">
          Ducat efficiency
        </h1>
        <p className="mt-1 max-w-[74ch] text-sm text-ink-400">
          The cheapest way to turn platinum into Baro ducats: items ranked by ducats per
          platinum spent. Stock these when you're sitting on plat and want ducats for the next
          void trader visit.
        </p>
      </header>
      <Panel title="Best ducats per plat" accent="var(--color-amber)">
        <AsyncBlock
          query={q}
          empty={(d) => d.items.length === 0}
          skeletonCols={4}
          emptyNode={
            <div className="surface px-5 py-8 text-center text-sm text-ink-400">
              No ducat data yet. Run{" "}
              <code className="nums text-ink-100">voidbroker ingest --details</code> first.
            </div>
          }
        >
          {(d) => <Table rows={d.items} />}
        </AsyncBlock>
      </Panel>
    </div>
  );
}
