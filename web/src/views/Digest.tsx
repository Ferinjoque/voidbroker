import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Gem, PackageOpen, Radar, Store, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";
import { api } from "../lib/api";
import { AsyncBlock, Pill, Thumb } from "../components/ui";
import { countdown, pct, plat } from "../lib/format";
import type { ViewId } from "../components/Sidebar";

function Section({
  title,
  icon,
  accent,
  to,
  onGo,
  children,
}: {
  title: string;
  icon: ReactNode;
  accent: string;
  to?: ViewId;
  onGo?: (v: ViewId) => void;
  children: ReactNode;
}) {
  return (
    <section className="surface flex flex-col p-5">
      <header className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span style={{ color: accent }}>{icon}</span>
          <h2 className="display text-sm font-semibold text-ink-100">{title}</h2>
        </div>
        {to && onGo && (
          <button
            onClick={() => onGo(to)}
            className="flex items-center gap-1 text-xs text-ink-600 transition-colors hover:text-gold"
          >
            all <ArrowRight size={12} />
          </button>
        )}
      </header>
      <div className="flex flex-col gap-2">{children}</div>
    </section>
  );
}

function Empty({ children }: { children: ReactNode }) {
  return <p className="text-xs text-ink-600">{children}</p>;
}

export function Digest({ onGo, onOpenItem }: { onGo: (v: ViewId) => void; onOpenItem: (slug: string, name?: string | null, thumb?: string | null) => void }) {
  const q = useQuery({ queryKey: ["digest"], queryFn: api.digest });

  return (
    <div>
      <header className="mb-6">
        <h1 className="display text-3xl font-semibold tracking-tight text-ink-50">Today</h1>
        <p className="mt-1 text-sm text-ink-400">
          The few things worth acting on right now, pulled from every signal layer.
        </p>
      </header>

      <AsyncBlock query={q}>
        {(d) => (
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <Section title="Buy opportunities" icon={<TrendingUp size={15} />} accent="var(--color-gold)" to="opportunities" onGo={onGo}>
              {d.opportunities.length ? (
                d.opportunities.map((o) => (
                  <button
                    key={o.slug}
                    onClick={() => onOpenItem(o.slug, o.name, o.thumb)}
                    className="flex items-center gap-2.5 rounded-md px-1.5 py-1 text-left transition-colors hover:bg-void-800/60"
                  >
                    <Thumb thumb={o.thumb} size={26} />
                    <span className="flex-1 truncate text-sm text-ink-100">{o.name ?? o.slug}</span>
                    <span className="nums text-sm text-gold">{plat(o.sell_min)}</span>
                    <span className="nums w-10 text-right text-xs text-up">{pct(o.margin_pct)}</span>
                  </button>
                ))
              ) : (
                <Empty>None — run an order-book ingest.</Empty>
              )}
            </Section>

            <Section title="Riven deals" icon={<Gem size={15} />} accent="var(--color-violet)" to="deals" onGo={onGo}>
              {d.riven_deals.length ? (
                d.riven_deals.map((x) => (
                  <div key={x.auction_id} className="flex items-center gap-2.5 px-1.5 py-1">
                    <span className="flex-1 truncate text-sm text-ink-100">
                      {x.weapon_name ?? x.weapon_slug}
                    </span>
                    <Pill tone={x.roll_label === "strong" ? "up" : "cyan"}>{x.roll_label}</Pill>
                    <span className="nums text-sm text-gold">{plat(x.price)}</span>
                    <span className="nums w-10 text-right text-xs text-up">{pct(x.discount_pct)}</span>
                  </div>
                ))
              ) : (
                <Empty>None — run a riven ingest.</Empty>
              )}
            </Section>

            <Section title="Disposition watch" icon={<Radar size={15} />} accent="var(--color-violet)" to="forecast" onGo={onGo}>
              {d.disposition_forecasts.length ? (
                d.disposition_forecasts.map((f) => (
                  <div key={f.slug} className="flex items-center gap-2.5 px-1.5 py-1">
                    <span className="flex-1 truncate text-sm text-ink-100">{f.name ?? f.slug}</span>
                    <Pill tone={f.direction === "nerf" ? "down" : "up"}>{f.direction}</Pill>
                    <span className="nums w-12 text-right text-xs text-ink-500">
                      {Math.round(f.confidence * 100)}%
                    </span>
                  </div>
                ))
              ) : (
                <Empty>No directional calls yet.</Empty>
              )}
            </Section>

            <Section title="Catalysts" icon={<PackageOpen size={15} />} accent="var(--color-amber)" to="resurgence" onGo={onGo}>
              {d.resurgence?.status.phase === "active" ? (
                <>
                  <div className="mb-1 text-xs text-ink-500">
                    Prime Resurgence re-vaults in{" "}
                    <span className="text-ink-200">
                      {countdown(d.resurgence.status.hours_until_rotation)}
                    </span>
                  </div>
                  {d.resurgence.best_buys.slice(0, 4).map((b) => (
                    <div key={b.slug} className="flex items-center gap-2.5 px-1.5 py-0.5">
                      <span className="flex-1 truncate text-sm text-ink-100">{b.item}</span>
                      <span className="nums text-sm text-gold">{plat(b.price_now)}</span>
                      {b.change_since_resurgence != null && b.change_since_resurgence < 0 && (
                        <span className="nums w-16 text-right text-xs text-up">
                          {pct(Math.abs(b.change_since_resurgence))} off
                        </span>
                      )}
                    </div>
                  ))}
                </>
              ) : (
                <Empty>No active resurgence rotation.</Empty>
              )}
              {d.void_trader?.phase === "active" && (
                <div className="mt-2 flex items-center gap-2 border-t border-void-800 pt-2 text-xs text-amber">
                  <Store size={13} /> Baro is here — leaves in{" "}
                  {countdown(d.void_trader.hours_until_departure)}
                </div>
              )}
            </Section>
          </div>
        )}
      </AsyncBlock>
    </div>
  );
}
