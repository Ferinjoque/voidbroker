import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, wfm, type DispositionChange } from "../lib/api";
import { AsyncBlock, FilterChip, PaginatedTable, Panel, Pill, type Column } from "../components/ui";
import { signed } from "../lib/format";

type DirFilter = "all" | "buff" | "nerf";

export function Disposition() {
  const q = useQuery({ queryKey: ["disposition-changes"], queryFn: api.dispositionChanges });
  const [dir, setDir] = useState<DirFilter>("all");

  return (
    <div>
      <header className="mb-6">
        <h1 className="display text-3xl font-semibold tracking-tight text-ink-50">
          Disposition moves
        </h1>
        <p className="mt-1 max-w-[72ch] text-sm text-ink-400">
          Changes in each riven’s strength multiplier, as observed over time. A rise is a
          <span className="text-up"> buff</span> (rivens gain value); a fall is a
          <span className="text-down"> nerf</span>. This is the dataset the predictor will learn
          to anticipate.
        </p>
      </header>

      <Panel
        title="Observed changes"
        accent="var(--color-violet)"
        actions={
          <div className="flex items-center gap-1">
            <FilterChip active={dir === "all"} onClick={() => setDir("all")}>
              All
            </FilterChip>
            <FilterChip active={dir === "buff"} onClick={() => setDir("buff")}>
              Buffs
            </FilterChip>
            <FilterChip active={dir === "nerf"} onClick={() => setDir("nerf")}>
              Nerfs
            </FilterChip>
          </div>
        }
      >
        <AsyncBlock
          query={q}
          empty={(d) => d.changes.length === 0}
          skeletonCols={5}
          emptyNode={
            <div className="surface px-5 py-10 text-center text-sm text-ink-400">
              No disposition moves recorded yet.
              <div className="mt-1.5 text-xs text-ink-600">
                Keep <code className="nums text-ink-100">voidbroker schedule</code> running to
                accumulate history.
              </div>
            </div>
          }
        >
          {(d) => {
            const columns: Column<DispositionChange>[] = [
              {
                key: "slug",
                header: "Weapon",
                render: (r) => (
                  <a
                    href={wfm.rivenAuctions(r.slug)}
                    target="_blank"
                    rel="noreferrer"
                    className="font-medium text-ink-100 transition-colors hover:text-gold"
                    title="View riven auctions on warframe.market"
                  >
                    {r.slug}
                  </a>
                ),
              },
              {
                key: "dir",
                header: "Move",
                render: (r) => <Pill tone={r.direction === "buff" ? "up" : "down"}>{r.direction}</Pill>,
              },
              {
                key: "from",
                header: "From",
                align: "right",
                render: (r) => <span className="text-ink-400">{r.from_disposition.toFixed(2)}</span>,
              },
              {
                key: "to",
                header: "To",
                align: "right",
                render: (r) => <span className="text-ink-100">{r.to_disposition.toFixed(2)}</span>,
              },
              {
                key: "delta",
                header: "Δ",
                align: "right",
                render: (r) => (
                  <span className={r.delta > 0 ? "text-up" : "text-down"}>{signed(r.delta)}</span>
                ),
              },
              {
                key: "at",
                header: "Observed",
                align: "right",
                render: (r) => <span className="text-ink-600">{r.at?.slice(0, 10)}</span>,
              },
            ];
            const rows = d.changes.filter((r) => dir === "all" || r.direction === dir);
            // key by the direction filter so switching it replays the row-in animation.
            return (
              <PaginatedTable
                key={dir}
                columns={columns}
                rows={rows}
                rowKey={(r) => `${r.slug}-${r.at}`}
              />
            );
          }}
        </AsyncBlock>
      </Panel>
    </div>
  );
}
