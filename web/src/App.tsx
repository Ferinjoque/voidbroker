import { useEffect, useState } from "react";
import { Digest } from "./views/Digest";
import { Dashboard } from "./views/Dashboard";
import { Forecast } from "./views/Forecast";
import { Opportunities } from "./views/Opportunities";
import { RivenDeals } from "./views/RivenDeals";
import { Disposition } from "./views/Disposition";
import { Backtests } from "./views/Backtests";
import { Arbitrage } from "./views/Arbitrage";
import { Ducats } from "./views/Ducats";
import { Journal } from "./views/Journal";
import { Baro } from "./views/Baro";
import { Resurgence } from "./views/Resurgence";
import { Markets } from "./views/Markets";
import { Watchlist } from "./views/Watchlist";
import { ItemDrawer, type DrawerTarget } from "./components/ItemDrawer";
import { Sidebar, type ViewId } from "./components/Sidebar";
import { CommandPalette } from "./components/CommandPalette";
import { parseHash, writeHash } from "./lib/route";

// Views are eager so each screen's header/chrome paints instantly on navigation; only the
// data regions below show skeletons (via AsyncBlock) while their queries resolve. The heavy
// chart library (lightweight-charts) is the one thing code-split, lazily imported inside
// PriceChart's consumers (Markets, ItemDrawer), so it never bloats the first paint.

export default function App() {
  // Seed from the URL so a refresh / shared link lands on the right view.
  const initial = parseHash();
  const [view, setView] = useState<ViewId>(initial.view);
  const [slug, setSlug] = useState(initial.slug); // empty -> Markets defaults to top-volume item
  const [drawer, setDrawer] = useState<DrawerTarget | null>(null);

  // Keep the hash in sync with state (replace on the very first write, push thereafter so
  // Back works), and react to back/forward by re-reading the hash.
  useEffect(() => {
    writeHash({ view, slug }, true);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    writeHash({ view, slug });
  }, [view, slug]);
  useEffect(() => {
    const onHashChange = () => {
      const r = parseHash();
      setView(r.view);
      setSlug(r.slug);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const openItemDetail = (s: string, name?: string | null, thumb?: string | null) =>
    setDrawer({ kind: "item", slug: s, name, thumb });
  const openChart = (s: string) => {
    setSlug(s);
    setView("markets");
  };

  return (
    <div className="flex min-h-screen">
      <Sidebar view={view} onSelect={setView} />

      <main className="min-w-0 flex-1 px-4 pt-16 pb-8 md:px-9 md:pt-8">
        {/* key={view} remounts on navigation so the page-enter animation re-fires
            for every screen change (Markets included). */}
        <div key={view} className="page-enter mx-auto max-w-[1140px]">
          {view === "digest" && <Digest onGo={setView} onOpenItem={openItemDetail} />}
          {view === "dashboard" && <Dashboard onOpenItem={openItemDetail} />}
          {view === "forecast" && <Forecast />}
          {view === "opportunities" && <Opportunities onOpenItem={openItemDetail} />}
          {view === "deals" && (
            <RivenDeals
              onOpenRiven={(deal) =>
                setDrawer({ kind: "riven", slug: deal.weapon_slug, name: deal.weapon_name, deal })
              }
            />
          )}
          {view === "disposition" && <Disposition />}
          {view === "backtests" && <Backtests />}
          {view === "arbitrage" && <Arbitrage />}
          {view === "ducats" && <Ducats />}
          {view === "journal" && <Journal />}
          {view === "baro" && <Baro />}
          {view === "resurgence" && <Resurgence />}
          {view === "markets" && <Markets slug={slug} onSlugChange={setSlug} />}
          {view === "watchlist" && <Watchlist onOpenItem={openItemDetail} />}
        </div>
      </main>

      {drawer && (
        <ItemDrawer target={drawer} onClose={() => setDrawer(null)} onOpenChart={openChart} />
      )}

      <CommandPalette onOpenItem={openItemDetail} onNavigate={setView} />
    </div>
  );
}
