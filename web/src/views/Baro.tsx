import { useQuery } from "@tanstack/react-query";
import { api, type VoidTraderItem } from "../lib/api";
import { AsyncBlock, PaginatedTable, Panel, Pill, type Column } from "../components/ui";
import { countdown } from "../lib/format";

export function Baro() {
  const q = useQuery({ queryKey: ["void-trader"], queryFn: api.voidTrader });

  return (
    <div>
      <header className="mb-6">
        <h1 className="display text-3xl font-semibold tracking-tight text-ink-50">
          Baro Ki’Teer
        </h1>
        <p className="mt-1 text-sm text-ink-400">
          The void trader, a scheduled catalyst. Items he carries swing in demand around each
          visit.
        </p>
      </header>

      <AsyncBlock query={q}>
        {(d) => {
          const s = d.status;
          const active = s.phase === "active";
          const big = active ? s.hours_until_departure : s.hours_until_arrival;
          const bigLabel = active ? "leaves in" : "arrives in";

          const columns: Column<VoidTraderItem>[] = [
            {
              key: "item",
              header: "Item",
              render: (r) => <span className="font-medium text-ink-100">{r.item}</span>,
            },
            {
              key: "ducats",
              header: "Ducats",
              align: "right",
              render: (r) => <span className="text-amber">{r.ducats.toLocaleString()}</span>,
            },
            {
              key: "credits",
              header: "Credits",
              align: "right",
              render: (r) => <span className="text-ink-300">{r.credits.toLocaleString()}</span>,
            },
          ];

          return (
            <div>
              <div className="surface mb-7 flex flex-wrap items-center gap-x-12 gap-y-5 px-7 py-6">
                <div>
                  <Pill tone={active ? "up" : "amber"}>{s.phase}</Pill>
                  <div className="mt-2.5 text-xs uppercase tracking-[0.08em] text-ink-600">
                    {bigLabel}
                  </div>
                  <div className="display text-5xl font-semibold text-ink-50">
                    {countdown(big)}
                  </div>
                </div>
                <div className="h-12 w-px bg-void-700" />
                <div className="space-y-1.5 text-sm">
                  <div className="text-ink-400">
                    Location <span className="ml-2 text-ink-100">{s.location ?? "—"}</span>
                  </div>
                  <div className="text-ink-400">
                    Inventory{" "}
                    <span className="ml-2 nums text-ink-100">{s.inventory_size}</span> items
                  </div>
                </div>
              </div>

              <Panel title="Inventory" accent="var(--color-amber)">
                {d.inventory.length > 0 ? (
                  <InventoryTable columns={columns} rows={d.inventory} />
                ) : (
                  <div className="surface px-5 py-8 text-center text-sm text-ink-400">
                    Inventory appears when he arrives. Until then, stockpile ducats for the items
                    you want.
                  </div>
                )}
              </Panel>
            </div>
          );
        }}
      </AsyncBlock>
    </div>
  );
}

function InventoryTable({ columns, rows }: { columns: Column<VoidTraderItem>[]; rows: VoidTraderItem[] }) {
  return <PaginatedTable columns={columns} rows={rows} rowKey={(r) => r.item} />;
}
