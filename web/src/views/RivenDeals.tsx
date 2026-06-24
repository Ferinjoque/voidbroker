import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type RivenDeal } from "../lib/api";
import {
  AsyncBlock,
  FilterChip,
  FilterInput,
  ItemName,
  Meter,
  PaginatedTable,
  Panel,
  Pill,
  type Column,
} from "../components/ui";
import { pct, plat } from "../lib/format";

type RollFilter = "all" | "quality" | "strong";
const ROLL_MIN: Record<RollFilter, number> = { all: 0, quality: 0.55, strong: 0.75 };

function prettySignature(sig: string): string {
  const [pos, neg] = sig.replace(/^\+/, "").split("|");
  const stats = pos.split(",").filter(Boolean).map((s) => s.replace(/_/g, " ")).join(", ");
  const negPart = neg === "+neg" ? "−" : neg === "noneg" ? "clean" : "";
  return stats + (negPart ? `  ·  ${negPart}` : "");
}

export function RivenDeals({ onOpenRiven }: { onOpenRiven: (deal: RivenDeal) => void }) {
  const q = useQuery({ queryKey: ["riven-deals"], queryFn: () => api.rivenDeals(true, 4, 0.25) });
  const [weaponFilter, setWeaponFilter] = useState("");
  const [roll, setRoll] = useState<RollFilter>("all");

  return (
    <div>
      <header className="mb-6">
        <h1 className="display text-3xl font-semibold tracking-tight text-ink-50">
          Undervalued rivens
        </h1>
        <p className="mt-1 max-w-[72ch] text-sm text-ink-400">
          Live listings priced below their comparables, grouped by positive stats and ranked with
          <span className="text-ink-300"> roll quality</span> factored in, so a god-roll priced like
          junk outranks something that is simply a weak roll. Still inspect the exact stats before
          buying.
        </p>
      </header>

      <Panel
        title="Discount scanner"
        caption="positives-only grouping, click any row for detail"
        accent="var(--color-violet)"
        actions={
          <div className="flex items-center gap-2">
            <FilterInput value={weaponFilter} onChange={setWeaponFilter} placeholder="Filter weapon…" />
            <FilterChip active={roll === "all"} onClick={() => setRoll("all")}>
              All rolls
            </FilterChip>
            <FilterChip active={roll === "quality"} onClick={() => setRoll("quality")}>
              Above avg+
            </FilterChip>
            <FilterChip active={roll === "strong"} onClick={() => setRoll("strong")}>
              Strong
            </FilterChip>
          </div>
        }
      >
        <AsyncBlock
          query={q}
          empty={(d) => d.deals.length === 0}
          skeletonCols={5}
          emptyNode={
            <div className="surface px-5 py-8 text-center text-sm text-ink-400">
              No riven deals yet. Run{" "}
              <code className="nums text-ink-100">voidbroker ingest --rivens</code> first.
            </div>
          }
        >
          {(d) => {
            const columns: Column<RivenDeal>[] = [
              {
                key: "weapon",
                header: "Weapon",
                render: (r) => <ItemName name={r.weapon_name} slug={r.weapon_slug} />,
              },
              {
                key: "sig",
                header: "Positives",
                render: (r) => <span className="text-ink-400">{prettySignature(r.signature)}</span>,
              },
              {
                key: "price",
                header: "Price",
                align: "right",
                render: (r) => <span className="text-gold">{plat(r.price)}</span>,
              },
              {
                key: "median",
                header: "Comp median",
                align: "right",
                render: (r) => <span className="text-ink-300">{plat(r.comparable_median)}</span>,
              },
              {
                key: "disc",
                header: "Discount",
                align: "right",
                width: "170px",
                render: (r) => (
                  <div className="flex items-center justify-end gap-2.5">
                    <div className="w-20">
                      <Meter value={r.discount_pct} color="var(--color-up)" />
                    </div>
                    <span className="w-10 text-right text-up">{pct(r.discount_pct)}</span>
                  </div>
                ),
              },
              {
                key: "roll",
                header: "Roll",
                render: (r) => {
                  const tone =
                    r.roll_label === "strong"
                      ? "up"
                      : r.roll_label === "above avg"
                        ? "cyan"
                        : r.roll_label === "weak"
                          ? "down"
                          : "neutral";
                  return <Pill tone={tone}>{r.roll_label}</Pill>;
                },
              },
              {
                key: "comps",
                header: "Comps",
                align: "right",
                render: (r) => <Pill tone="cyan">{r.comparable_count}</Pill>,
              },
            ];
            const wf = weaponFilter.trim().toLowerCase();
            const rows = d.deals.filter(
              (r) =>
                r.roll_quality >= ROLL_MIN[roll] &&
                (!wf ||
                  (r.weapon_name ?? r.weapon_slug).toLowerCase().includes(wf) ||
                  r.weapon_slug.includes(wf)),
            );
            if (rows.length === 0) {
              return (
                <div className="surface px-5 py-8 text-center text-sm text-ink-400">
                  No deals match the current filters.
                </div>
              );
            }
            // key by the roll chip so changing it remounts the table and replays the
            // row-entrance stagger (otherwise surviving rows teleport into place).
            return (
              <PaginatedTable
                key={roll}
                columns={columns}
                rows={rows}
                rowKey={(r) => r.auction_id}
                onRowClick={onOpenRiven}
                exportName="voidbroker-riven-deals"
              />
            );
          }}
        </AsyncBlock>
      </Panel>
    </div>
  );
}
