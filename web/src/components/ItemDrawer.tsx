import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, wfm, type RivenDeal } from "../lib/api";
import { Pill, SkeletonRows, StarButton, Thumb } from "./ui";
import { plat } from "../lib/format";
import { useFocusTrap } from "../hooks/useFocusTrap";

// Code-split the chart library; the drawer's header + order book paint without it.
const PriceChart = lazy(() => import("./PriceChart").then((m) => ({ default: m.PriceChart })));

export type DrawerTarget =
  | { kind: "item"; slug: string; name?: string | null; thumb?: string | null }
  | { kind: "riven"; slug: string; name?: string | null; deal: RivenDeal };

function prettySignature(sig: string): string {
  const [pos, neg] = sig.replace(/^\+/, "").split("|");
  const stats = pos.split(",").filter(Boolean).map((s) => s.replace(/_/g, " ")).join(", ");
  const negPart = neg === "+neg" ? " (has a negative)" : neg === "noneg" ? " (no negative)" : "";
  return stats + negPart;
}

function ExternalButton({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="inline-flex items-center gap-1.5 rounded-lg border border-void-700 bg-void-800 px-3.5 py-2 text-sm font-medium text-ink-100 transition-colors hover:border-gold hover:text-gold"
    >
      {children}
      <span aria-hidden className="text-xs">↗</span>
    </a>
  );
}

/** A compact order-book preview built from the stored snapshot, evoking the
    warframe.market listing without leaving the terminal. */
function MarketPreview({ slug }: { slug: string }) {
  const q = useQuery({ queryKey: ["orderbook", slug], queryFn: () => api.orderbook(slug) });
  if (q.isPending) return <SkeletonRows rows={4} cols={2} />;
  if (q.isError)
    return <p className="text-sm text-ink-600">No live order snapshot stored for this item.</p>;
  const o = q.data;
  const asks = [
    { label: "median", v: o.sell_median },
    { label: "p25", v: o.sell_p25 },
    { label: "lowest", v: o.sell_min },
  ].filter((a) => a.v != null);

  return (
    <div className="surface p-4">
      <div className="mb-3 flex items-center justify-between text-[11px] uppercase tracking-[0.08em] text-ink-600">
        <span>Order book preview</span>
        <span className="nums">
          {o.n_sell_live} sellers / {o.n_buy_live} buyers online
        </span>
      </div>
      <div className="grid grid-cols-2 gap-5">
        <div>
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-down">
            Want to sell
          </div>
          {asks.map((a) => (
            <div key={a.label} className="flex items-center justify-between py-0.5 text-sm">
              <span className="text-ink-600">{a.label}</span>
              <span className="nums text-ink-100">{plat(a.v)}</span>
            </div>
          ))}
        </div>
        <div>
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-up">
            Want to buy
          </div>
          <div className="flex items-center justify-between py-0.5 text-sm">
            <span className="text-ink-600">highest</span>
            <span className="nums text-ink-100">{plat(o.buy_max)}</span>
          </div>
          <div className="flex items-center justify-between py-0.5 text-sm">
            <span className="text-ink-600">spread</span>
            <span className="nums text-gold">{plat(o.spread)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

function ItemBody({ slug }: { slug: string }) {
  const q = useQuery({ queryKey: ["prices", slug], queryFn: () => api.itemPrices(slug) });
  return (
    <div className="space-y-5">
      <div className="surface p-3">
        {q.isPending && <SkeletonRows rows={6} cols={1} />}
        {q.isError && <p className="px-2 py-8 text-center text-sm text-ink-400">No price history.</p>}
        {q.data && q.data.series.length > 0 && (
          <Suspense fallback={<SkeletonRows rows={6} cols={1} />}>
            <PriceChart bars={q.data.series} />
          </Suspense>
        )}
      </div>
      <MarketPreview slug={slug} />
      <div className="flex gap-2.5">
        <ExternalButton href={wfm.item(slug)}>Open on warframe.market</ExternalButton>
      </div>
    </div>
  );
}

function RivenBody({ deal }: { deal: RivenDeal }) {
  const rows: [string, React.ReactNode][] = [
    ["Asking price", <span className="nums text-gold">{plat(deal.price)}</span>],
    ["Comparable median", <span className="nums text-ink-100">{plat(deal.comparable_median)}</span>],
    [
      "Discount",
      <span className="nums text-up">{Math.round(deal.discount_pct * 100)}%</span>,
    ],
    [
      "Roll quality",
      <Pill tone={deal.roll_label === "strong" ? "up" : deal.roll_label === "weak" ? "down" : "cyan"}>
        {deal.roll_label} · {Math.round(deal.roll_quality * 100)}%
      </Pill>,
    ],
    ["Comparables", <span className="nums text-ink-100">{deal.comparable_count}</span>],
    ["Seller", <Pill tone={deal.owner_status === "ingame" ? "up" : "cyan"}>{deal.owner_status}</Pill>],
  ];
  return (
    <div className="space-y-5">
      <div className="surface p-4">
        <div className="mb-2 text-[11px] uppercase tracking-[0.08em] text-ink-600">Positives</div>
        <div className="text-sm text-ink-100">{prettySignature(deal.signature)}</div>
      </div>
      <div className="surface p-4">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-center justify-between border-t border-void-800/60 py-2 text-sm first:border-t-0">
            <span className="text-ink-400">{k}</span>
            {v}
          </div>
        ))}
      </div>
      <p className="text-xs text-ink-600">
        Roll quality is scored against the comparable group, but grouping is by positive stats
        only. Open the live auctions to confirm the exact roll before buying.
      </p>
      <div className="flex gap-2.5">
        <ExternalButton href={wfm.rivenAuctions(deal.weapon_slug)}>
          Open riven auctions on warframe.market
        </ExternalButton>
      </div>
    </div>
  );
}

export function ItemDrawer({
  target,
  onClose,
  onOpenChart,
}: {
  target: DrawerTarget;
  onClose: () => void;
  onOpenChart?: (slug: string) => void;
}) {
  const [closing, setClosing] = useState(false);
  const asideRef = useRef<HTMLElement>(null);
  const close = () => setClosing(true);

  // Trap focus in the drawer and return it to the trigger on unmount. Active while open
  // (not closing) so Tab stays inside; the trap's cleanup restores focus when it unmounts.
  useFocusTrap(asideRef, !closing);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setClosing(true);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // After the exit animation plays, unmount. Must match --dur-exit (240ms).
  useEffect(() => {
    if (!closing) return;
    const t = setTimeout(onClose, 240);
    return () => clearTimeout(t);
  }, [closing, onClose]);

  const title = target.name ?? target.slug;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div
        className={`${closing ? "fade-out" : "fade-in"} absolute inset-0 bg-void-950/70 backdrop-blur-[2px]`}
        onClick={close}
      />
      <aside
        ref={asideRef}
        role="dialog"
        aria-modal="true"
        aria-label={`${title} detail`}
        className={`${closing ? "slide-out" : "slide-in"} relative flex h-full w-[500px] max-w-[92vw] flex-col border-l border-void-700 bg-void-900 shadow-2xl`}
      >
        <header className="flex items-start justify-between gap-4 border-b border-void-800 px-6 py-5">
          <div className="flex items-center gap-3">
            {target.kind === "item" && <Thumb thumb={target.thumb} size={40} />}
            <div>
              <div className="flex items-center gap-2.5">
                <h2 className="display text-xl font-semibold text-ink-50">{title}</h2>
                <Pill tone={target.kind === "riven" ? "violet" : "cyan"}>{target.kind}</Pill>
                {target.kind === "item" && <StarButton slug={target.slug} size={16} />}
              </div>
              <div className="nums mt-0.5 text-xs text-ink-700">{target.slug}</div>
            </div>
          </div>
          <button
            onClick={close}
            aria-label="Close"
            className="rounded-md px-2 py-1 text-lg text-ink-400 transition-colors hover:bg-void-800 hover:text-ink-100"
          >
            ✕
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-6 py-5">
          {target.kind === "item" ? <ItemBody slug={target.slug} /> : <RivenBody deal={target.deal} />}
        </div>

        {target.kind === "item" && onOpenChart && (
          <footer className="border-t border-void-800 px-6 py-3.5">
            <button
              onClick={() => {
                onOpenChart(target.slug);
                close();
              }}
              className="text-sm text-gold transition-colors hover:text-gold-dim"
            >
              Open full chart in Markets →
            </button>
          </footer>
        )}
      </aside>
    </div>
  );
}
