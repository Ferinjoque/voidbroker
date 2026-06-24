import { useQuery } from "@tanstack/react-query";
import { api, type SetArbitrage } from "../lib/api";
import { AsyncBlock, Meter, PaginatedTable, Panel, Pill, type Column } from "../components/ui";
import { pct, plat } from "../lib/format";

function Table({ rows }: { rows: SetArbitrage[] }) {
  const maxMargin = Math.max(...rows.map((r) => r.margin_pct), 0.0001);
  const columns: Column<SetArbitrage>[] = [
    {
      key: "set",
      header: "Set",
      render: (r) => <span className="font-medium text-ink-100">{r.name ?? r.slug}</span>,
    },
    {
      key: "do",
      header: "Play",
      render: (r) =>
        r.direction === "build" ? (
          <Pill tone="cyan">buy parts → sell set</Pill>
        ) : (
          <Pill tone="violet">buy set → sell parts</Pill>
        ),
    },
    {
      key: "set_price",
      header: "Set",
      align: "right",
      render: (r) => <span className="text-ink-300">{plat(r.set_price)}</span>,
    },
    {
      key: "parts",
      header: "Parts sum",
      align: "right",
      render: (r) => (
        <span className="text-ink-300">
          {plat(r.parts_cost)} <span className="text-ink-700">/ {r.n_parts}</span>
        </span>
      ),
    },
    {
      key: "profit",
      header: "Profit",
      align: "right",
      render: (r) => <span className="text-up">{plat(r.profit)}p</span>,
    },
    {
      key: "margin",
      header: "Margin",
      align: "right",
      width: "160px",
      render: (r) => (
        <div className="flex items-center justify-end gap-2.5">
          <div className="w-20">
            <Meter value={r.margin_pct / maxMargin} color="var(--color-up)" />
          </div>
          <span className="w-12 text-right text-up">{pct(r.margin_pct)}</span>
        </div>
      ),
    },
  ];
  return (
    <PaginatedTable
      columns={columns}
      rows={rows}
      rowKey={(r) => r.slug}
      exportName="voidbroker-set-arbitrage"
    />
  );
}

export function Arbitrage() {
  const q = useQuery({ queryKey: ["set-arbitrage"], queryFn: api.setArbitrage });
  return (
    <div>
      <header className="mb-6">
        <h1 className="display text-3xl font-semibold tracking-tight text-ink-50">
          Set arbitrage
        </h1>
        <p className="mt-1 max-w-[74ch] text-sm text-ink-400">
          A Prime set is just its parts. When the set price and the summed part prices diverge,
          there's a flip:{" "}
          <span className="text-cyan">buy the parts and sell the assembled set</span>, or{" "}
          <span className="text-violet">buy the set and relist the parts</span>. Only sets with
          every part priced are shown.
        </p>
      </header>
      <Panel title="Build / split flips" caption="ranked by margin on the side you buy" accent="var(--color-up)">
        <AsyncBlock
          query={q}
          empty={(d) => d.deals.length === 0}
          skeletonCols={6}
          emptyNode={
            <div className="surface px-5 py-8 text-center text-sm text-ink-400">
              No set arbitrage right now. Needs item details +{" "}
              <code className="nums text-ink-100">ingest --details</code> and price history.
            </div>
          }
        >
          {(d) => <Table rows={d.deals} />}
        </AsyncBlock>
      </Panel>
    </div>
  );
}
