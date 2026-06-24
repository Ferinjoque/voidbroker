import { useQuery } from "@tanstack/react-query";
import { api, type Opportunity } from "../lib/api";
import {
  AsyncBlock,
  ItemName,
  Meter,
  PaginatedTable,
  Panel,
  Sparkline,
  type Column,
} from "../components/ui";
import { flip, pct, plat } from "../lib/format";

export function Opportunities({
  onOpenItem,
}: {
  onOpenItem: (slug: string, name?: string | null, thumb?: string | null) => void;
}) {
  const q = useQuery({ queryKey: ["opportunities"], queryFn: () => api.opportunities(0.05) });

  return (
    <div>
      <header className="mb-6">
        <h1 className="display text-3xl font-semibold tracking-tight text-ink-50">
          Buy opportunities
        </h1>
        <p className="mt-1 max-w-[68ch] text-sm text-ink-400">
          Items whose best live sell sits below their recent baseline, ranked by
          <span className="text-ink-300"> margin × liquidity ÷ flip-time</span>. A fat margin
          on something that never trades loses to a thinner one that flips in a day.
        </p>
      </header>

      <Panel title="Ranked signals" caption="click any row for detail">
        <AsyncBlock
          query={q}
          empty={(d) => d.opportunities.length === 0}
          skeletonCols={7}
          emptyNode={
            <div className="surface px-5 py-8 text-center text-sm text-ink-400">
              No opportunities yet. Run{" "}
              <code className="nums text-ink-100">voidbroker ingest --orders</code> first.
            </div>
          }
        >
          {(d) => {
            const maxScore = Math.max(...d.opportunities.map((o) => o.score), 0.0001);
            const columns: Column<Opportunity>[] = [
              {
                key: "slug",
                header: "Item",
                render: (r) => <ItemName name={r.name} slug={r.slug} thumb={r.thumb} />,
              },
              {
                key: "trend",
                header: "Trend",
                width: "92px",
                render: (r) => <Sparkline data={r.spark} width={76} />,
              },
              {
                key: "buy",
                header: "Buy @",
                align: "right",
                render: (r) => <span className="text-gold">{plat(r.sell_min)}</span>,
              },
              { key: "base", header: "Baseline", align: "right", render: (r) => plat(r.baseline) },
              {
                key: "margin",
                header: "Margin",
                align: "right",
                render: (r) => (
                  <span className="text-up">
                    {plat(r.margin)}{" "}
                    <span className="text-up-dim">{pct(r.margin_pct)}</span>
                  </span>
                ),
              },
              {
                key: "liq",
                header: "Vol/day",
                align: "right",
                render: (r) => <span className="text-ink-300">{r.liquidity.toFixed(0)}</span>,
              },
              {
                key: "flip",
                header: "Flip",
                align: "right",
                render: (r) => <span className="text-ink-300">{flip(r.flip_days_est)}</span>,
              },
              {
                key: "score",
                header: "Score",
                align: "right",
                width: "150px",
                render: (r) => (
                  <div className="flex items-center justify-end gap-2.5">
                    <div className="w-20">
                      <Meter value={r.score / maxScore} color="var(--color-gold)" />
                    </div>
                    <span className="w-14 text-right text-ink-400">{r.score.toFixed(4)}</span>
                  </div>
                ),
              },
            ];
            return (
              <PaginatedTable
                columns={columns}
                rows={d.opportunities}
                rowKey={(r) => r.slug}
                onRowClick={(r) => onOpenItem(r.slug, r.name, r.thumb)}
                exportName="voidbroker-opportunities"
              />
            );
          }}
        </AsyncBlock>
      </Panel>
    </div>
  );
}
