import { useQuery } from "@tanstack/react-query";
import { api, type ResurgenceImpact, type ResurgenceItem } from "../lib/api";
import { AsyncBlock, PaginatedTable, Panel, Pill, type Column } from "../components/ui";
import { countdown, pct, plat } from "../lib/format";

const isPack = (i: ResurgenceItem) =>
  /package/i.test(i.unique_name ?? "") || /pack/i.test(i.item);

interface Row {
  item: string;
  ducats: number;
  impact: ResurgenceImpact | undefined;
}

function UnvaultedTable({ rows }: { rows: Row[] }) {
  const columns: Column<Row>[] = [
    {
      key: "item",
      header: "Unvaulted Prime",
      render: (r) => (
        <div className="leading-tight">
          <div className="font-medium text-ink-100">{r.item}</div>
          {r.impact && <div className="nums text-[11px] text-ink-700">{r.impact.slug}</div>}
        </div>
      ),
    },
    {
      key: "aya",
      header: "Aya",
      align: "right",
      render: (r) => <span className="text-violet">{r.ducats.toLocaleString()}</span>,
    },
    {
      key: "price",
      header: "Plat now",
      align: "right",
      render: (r) =>
        r.impact?.price_now != null ? (
          <span className="text-gold">{plat(r.impact.price_now)}</span>
        ) : (
          <span className="text-ink-700">—</span>
        ),
    },
    {
      key: "change",
      header: "Since resurgence",
      align: "right",
      render: (r) => {
        const c = r.impact?.change_since_resurgence;
        if (c == null) return <span className="text-ink-700">—</span>;
        const down = c < 0;
        return (
          <span className={down ? "text-up" : c > 0 ? "text-down" : "text-ink-400"}>
            {down ? "▼" : c > 0 ? "▲" : ""} {pct(Math.abs(c))}
            {down && <span className="ml-1 text-[11px] text-ink-600">cheaper</span>}
          </span>
        );
      },
    },
  ];
  return <PaginatedTable columns={columns} rows={rows} rowKey={(r) => r.item} />;
}

export function Resurgence() {
  const q = useQuery({ queryKey: ["resurgence"], queryFn: api.resurgence });

  return (
    <div>
      <header className="mb-6">
        <h1 className="display text-3xl font-semibold tracking-tight text-ink-50">
          Prime Resurgence
        </h1>
        <p className="mt-1 max-w-[74ch] text-sm text-ink-400">
          Varzia rotates vaulted Primes back into reach for a window. While they are available,
          supply rises and plat softens, so it is the moment to accumulate. Once they re-vault,
          scarcity pushes prices back up.
        </p>
      </header>

      <AsyncBlock query={q}>
        {(d) => {
          const s = d.status;
          const active = s.phase === "active";
          const big = active ? s.hours_until_rotation : s.hours_until_start;
          const bigLabel = active ? "re-vaults in" : "starts in";
          const impactByItem = new Map(d.impact.map((i) => [i.item, i]));
          const rows: Row[] = d.inventory
            .filter((i) => !isPack(i))
            .map((i) => ({ item: i.item, ducats: i.ducats, impact: impactByItem.get(i.item) }))
            // Matched, dipped items first (the actionable ones), then the rest.
            .sort((a, b) => {
              const ca = a.impact?.change_since_resurgence ?? 1;
              const cb = b.impact?.change_since_resurgence ?? 1;
              return ca - cb;
            });
          const matchedCount = rows.filter((r) => r.impact).length;

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
                    Trader <span className="ml-2 text-ink-100">{s.character ?? "Varzia"}</span>
                  </div>
                  <div className="text-ink-400">
                    Unvaulted{" "}
                    <span className="ml-2 nums text-ink-100">{s.item_count}</span> Primes
                  </div>
                </div>
                {active && (
                  <p className="max-w-[34ch] text-xs leading-relaxed text-ink-500">
                    Buy these now while supply is high; they tend to appreciate once the window
                    closes and they return to the vault.
                  </p>
                )}
              </div>

              <Panel
                title="Unvaulted now"
                caption={
                  matchedCount > 0
                    ? `${matchedCount} linked to market prices`
                    : "price linking fills in as the catalog matches"
                }
                accent="var(--color-violet)"
              >
                {rows.length > 0 ? (
                  <UnvaultedTable rows={rows} />
                ) : (
                  <div className="surface px-5 py-8 text-center text-sm text-ink-400">
                    No active rotation. Check back when Varzia refreshes her offerings.
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
