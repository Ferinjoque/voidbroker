import { useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { api, type ItemSearchResult, type Position, type Trade } from "../lib/api";
import { useItemSearch } from "../hooks/useItemSearch";
import {
  AsyncBlock,
  ItemName,
  PaginatedTable,
  Panel,
  Pill,
  Thumb,
  type Column,
} from "../components/ui";
import { plat } from "../lib/format";

const signedPlat = (v: number | null | undefined) =>
  v == null ? "—" : `${v >= 0 ? "+" : "−"}${plat(Math.abs(v))}p`;
const tone = (v: number | null | undefined) =>
  v == null ? "text-ink-400" : v > 0 ? "text-up" : v < 0 ? "text-down" : "text-ink-400";

function Stat({ label, value, valueTone }: { label: string; value: ReactNode; valueTone?: string }) {
  return (
    <div>
      <div className="text-[10.5px] uppercase tracking-[0.08em] text-ink-600">{label}</div>
      <div className={`display mt-0.5 text-2xl ${valueTone ?? "text-ink-50"}`}>{value}</div>
    </div>
  );
}

function AddTradeForm({ onAdded }: { onAdded: () => void }) {
  const [picked, setPicked] = useState<ItemSearchResult | null>(null);
  const [open, setOpen] = useState(false);
  const { query: q, setQuery: setQ, results } = useItemSearch(open);
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [qty, setQty] = useState("1");
  const [price, setPrice] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const add = useMutation({
    mutationFn: () =>
      api.addTrade({
        slug: picked!.slug,
        side,
        quantity: Number(qty),
        price: Number(price),
      }),
    onSuccess: () => {
      setPicked(null);
      setQ("");
      setQty("1");
      setPrice("");
      setErr(null);
      onAdded();
    },
    onError: (e: Error) => setErr(e.message),
  });

  const valid = picked && Number(qty) >= 1 && Number(price) >= 0 && price !== "";

  return (
    <div className="surface mb-7 p-5">
      <div className="mb-3 text-[11px] uppercase tracking-[0.08em] text-ink-600">Log a trade</div>
      <div className="flex flex-wrap items-end gap-3">
        <div className="relative">
          <label className="mb-1 block text-xs text-ink-500">Item</label>
          {picked ? (
            <button
              onClick={() => setPicked(null)}
              className="flex h-[38px] items-center gap-2 rounded-md border border-void-700 bg-void-850 px-2.5 text-sm text-ink-100"
            >
              <Thumb thumb={picked.thumb} size={22} />
              {picked.name ?? picked.slug}
              <span className="text-ink-700">✕</span>
            </button>
          ) : (
            <>
              <input
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setOpen(true);
                }}
                onFocus={() => setOpen(true)}
                onBlur={() => setTimeout(() => setOpen(false), 150)}
                placeholder="Search item…"
                spellCheck={false}
                className="w-56 rounded-md border border-void-700 bg-void-850/70 px-3 py-2 text-sm text-ink-100 outline-none focus:border-gold"
              />
              {open && results.length > 0 && (
                <ul className="absolute z-20 mt-1 max-h-64 w-72 overflow-auto rounded-md border border-void-700 bg-void-850 p-1 shadow-2xl">
                  {results.map((r) => (
                    <li key={r.slug}>
                      <button
                        onMouseDown={(e) => e.preventDefault()}
                        onClick={() => {
                          setPicked(r);
                          setOpen(false);
                        }}
                        className="flex w-full items-center gap-2.5 rounded px-2 py-1.5 text-left hover:bg-void-800"
                      >
                        <Thumb thumb={r.thumb} size={22} />
                        <span className="text-sm text-ink-100">{r.name ?? r.slug}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
        <div>
          <label className="mb-1 block text-xs text-ink-500">Side</label>
          <div className="flex overflow-hidden rounded-md border border-void-700">
            {(["buy", "sell"] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSide(s)}
                className={`px-3 py-2 text-sm transition-colors ${
                  side === s
                    ? s === "buy"
                      ? "bg-up/20 text-up"
                      : "bg-down/20 text-down"
                    : "text-ink-500 hover:bg-void-800"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="mb-1 block text-xs text-ink-500">Qty</label>
          <input
            type="number"
            min={1}
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            className="nums w-20 rounded-md border border-void-700 bg-void-850/70 px-3 py-2 text-sm text-ink-100 outline-none focus:border-gold"
          />
        </div>
        <div>
          <label className="mb-1 block text-xs text-ink-500">Plat each</label>
          <input
            type="number"
            min={0}
            value={price}
            onChange={(e) => setPrice(e.target.value)}
            placeholder="0"
            className="nums w-24 rounded-md border border-void-700 bg-void-850/70 px-3 py-2 text-sm text-ink-100 outline-none focus:border-gold"
          />
        </div>
        <button
          disabled={!valid || add.isPending}
          onClick={() => add.mutate()}
          className="rounded-md bg-gold px-4 py-2 text-sm font-medium text-void-950 transition-opacity hover:opacity-90 disabled:opacity-40"
        >
          {add.isPending ? "…" : "Add"}
        </button>
      </div>
      {err && <div className="mt-2 text-xs text-down">{err}</div>}
    </div>
  );
}

export function Journal() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["journal"], queryFn: api.journal });
  const refresh = () => qc.invalidateQueries({ queryKey: ["journal"] });
  const [delErr, setDelErr] = useState<string | null>(null);
  const del = useMutation({
    mutationFn: (id: number) => api.deleteTrade(id),
    onSuccess: () => {
      setDelErr(null);
      refresh();
    },
    onError: (e: Error) => setDelErr(e.message),
  });

  return (
    <div>
      <header className="mb-6">
        <h1 className="display text-3xl font-semibold tracking-tight text-ink-50">Journal</h1>
        <p className="mt-1 max-w-[74ch] text-sm text-ink-400">
          Log what you actually buy and sell. Realized P&amp;L is FIFO; open positions are valued
          against the current market for unrealized P&amp;L. Did the signals make you plat?
        </p>
      </header>

      <AddTradeForm onAdded={refresh} />

      <AsyncBlock query={q}>
        {(d) => {
          const s = d.summary;
          return (
            <>
              <div className="surface mb-7 flex flex-wrap items-center gap-x-12 gap-y-4 px-7 py-5">
                <Stat label="Realized" value={signedPlat(s.realized_pnl)} valueTone={tone(s.realized_pnl)} />
                <Stat
                  label="Unrealized"
                  value={signedPlat(s.unrealized_pnl)}
                  valueTone={tone(s.unrealized_pnl)}
                />
                <Stat label="Total" value={signedPlat(s.total_pnl)} valueTone={tone(s.total_pnl)} />
                <div className="h-10 w-px bg-void-700" />
                <Stat label="Trades" value={s.n_trades} />
                <Stat label="Open positions" value={s.open_positions.length} />
              </div>

              <Panel title="Open positions" accent="var(--color-cyan)">
                {s.open_positions.length ? (
                  <PositionsTable rows={s.open_positions} />
                ) : (
                  <div className="surface px-5 py-7 text-center text-sm text-ink-400">
                    No open positions. Log a buy above.
                  </div>
                )}
              </Panel>

              <Panel title="Trade log" accent="var(--color-gold)">
                {delErr && <div className="mb-2 px-1 text-xs text-down">Delete failed: {delErr}</div>}
                {d.trades.length ? (
                  <TradesTable rows={[...d.trades].reverse()} onDelete={(id) => del.mutate(id)} />
                ) : (
                  <div className="surface px-5 py-7 text-center text-sm text-ink-400">
                    No trades logged yet.
                  </div>
                )}
              </Panel>
            </>
          );
        }}
      </AsyncBlock>
    </div>
  );
}

function PositionsTable({ rows }: { rows: Position[] }) {
  const columns: Column<Position>[] = [
    { key: "slug", header: "Item", render: (r) => <ItemName slug={r.slug} /> },
    { key: "qty", header: "Qty", align: "right", render: (r) => r.quantity },
    { key: "avg", header: "Avg cost", align: "right", render: (r) => plat(r.avg_cost) },
    {
      key: "price",
      header: "Market",
      align: "right",
      render: (r) => (r.price == null ? "—" : plat(r.price)),
    },
    {
      key: "u",
      header: "Unrealized",
      align: "right",
      render: (r) => <span className={tone(r.unrealized)}>{signedPlat(r.unrealized)}</span>,
    },
  ];
  return <PaginatedTable columns={columns} rows={rows} rowKey={(r) => r.slug} pageSize={12} />;
}

function TradesTable({ rows, onDelete }: { rows: Trade[]; onDelete: (id: number) => void }) {
  const columns: Column<Trade>[] = [
    {
      key: "side",
      header: "Side",
      render: (r) => <Pill tone={r.side === "buy" ? "up" : "down"}>{r.side}</Pill>,
    },
    { key: "slug", header: "Item", render: (r) => <span className="text-ink-100">{r.slug}</span> },
    { key: "qty", header: "Qty", align: "right", render: (r) => r.quantity },
    { key: "price", header: "Plat each", align: "right", render: (r) => plat(r.price) },
    {
      key: "when",
      header: "When",
      align: "right",
      render: (r) => <span className="text-ink-600">{r.traded_at?.slice(0, 10)}</span>,
    },
    {
      key: "del",
      header: "",
      align: "right",
      width: "44px",
      render: (r) => (
        <button
          onClick={() => onDelete(r.id)}
          aria-label="Delete trade"
          className="text-ink-600 transition-colors hover:text-down"
        >
          <Trash2 size={14} />
        </button>
      ),
    },
  ];
  return <PaginatedTable columns={columns} rows={rows} rowKey={(r) => String(r.id)} pageSize={12} />;
}
