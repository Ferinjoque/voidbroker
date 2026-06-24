import {
  Activity,
  CandlestickChart,
  Coins,
  FlaskConical,
  Gem,
  LayoutDashboard,
  Newspaper,
  PackageOpen,
  Radar,
  Repeat,
  Star,
  Store,
  TrendingUp,
  Wallet,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  id: string;
  label: string;
  group: string;
  icon: LucideIcon;
}

// Single source of truth for the nav. Kept in its own module (not Sidebar.tsx) so the
// component file only exports a component — keeps react-refresh happy and lets App import
// ViewId without pulling in the whole sidebar.
export const NAV: NavItem[] = [
  { id: "digest", label: "Today", group: "Overview", icon: Newspaper },
  { id: "dashboard", label: "Dashboard", group: "Overview", icon: LayoutDashboard },
  { id: "markets", label: "Markets", group: "Overview", icon: CandlestickChart },
  { id: "watchlist", label: "Watchlist", group: "Overview", icon: Star },
  { id: "forecast", label: "Forecast", group: "Signals", icon: Radar },
  { id: "opportunities", label: "Opportunities", group: "Signals", icon: TrendingUp },
  { id: "deals", label: "Riven Deals", group: "Signals", icon: Gem },
  { id: "disposition", label: "Disposition", group: "Signals", icon: Activity },
  { id: "backtests", label: "Validation", group: "Signals", icon: FlaskConical },
  { id: "arbitrage", label: "Arbitrage", group: "Flips", icon: Repeat },
  { id: "ducats", label: "Ducats", group: "Flips", icon: Coins },
  { id: "journal", label: "Journal", group: "Portfolio", icon: Wallet },
  { id: "baro", label: "Baro", group: "Catalysts", icon: Store },
  { id: "resurgence", label: "Resurgence", group: "Catalysts", icon: PackageOpen },
];

export type ViewId = (typeof NAV)[number]["id"];
