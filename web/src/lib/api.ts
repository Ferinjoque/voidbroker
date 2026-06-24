/** Typed client for the voidbroker read API. */

const BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? "http://127.0.0.1:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText}: ${path}`);
  }
  return res.json() as Promise<T>;
}

async function send<T>(path: string, method: "POST" | "DELETE", body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const j = await res.json();
      if (j?.detail) detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export interface Summary {
  items: number;
  riven_weapons: number;
  price_rows: number;
  disposition_rows: number;
  order_snapshots: number;
  riven_auctions: number;
  void_trader_snapshots: number;
}

export interface VolumeRow {
  slug: string;
  name: string | null;
  thumb: string | null;
  datetime: string;
  volume: number;
  median: number | null;
  moving_avg: number | null;
  spark: number[];
}

export interface ItemSearchResult {
  slug: string;
  name: string | null;
  thumb: string | null;
}

export interface Opportunity {
  slug: string;
  name: string | null;
  thumb: string | null;
  sell_min: number;
  baseline: number;
  margin: number;
  margin_pct: number;
  liquidity: number;
  flip_days_est: number;
  score: number;
  spark: number[];
}

export interface RivenDeal {
  auction_id: string;
  weapon_slug: string;
  weapon_name: string | null;
  signature: string;
  price: number;
  comparable_median: number;
  discount_pct: number;
  comparable_count: number;
  owner_status: string;
  roll_quality: number;
  roll_label: string;
  score: number;
}

export interface DispositionChange {
  slug: string;
  from_disposition: number;
  to_disposition: number;
  delta: number;
  direction: "buff" | "nerf";
  at: string;
}

export interface DispositionForecast {
  slug: string;
  name: string | null;
  current_disposition: number;
  direction: "buff" | "nerf" | "stable";
  pressure: number;
  confidence: number;
  reasons: string[];
  n_history: number;
  demand: number | null;
}

export interface VoidTraderStatus {
  character: string | null;
  location: string | null;
  phase: "active" | "incoming" | "unknown";
  hours_until_arrival: number | null;
  hours_until_departure: number | null;
  inventory_size: number;
}

export interface VoidTraderItem {
  item: string;
  ducats: number;
  credits: number;
}

export interface ResurgenceStatus {
  character: string | null;
  phase: "active" | "upcoming" | "unknown";
  hours_until_rotation: number | null;
  hours_until_start: number | null;
  item_count: number;
}

export interface ResurgenceItem {
  item: string;
  ducats: number;
  unique_name: string | null;
}

export interface ResurgenceImpact {
  item: string;
  slug: string;
  price_now: number | null;
  price_before: number | null;
  change_since_resurgence: number | null;
}

export interface PriceBar {
  datetime: string;
  open_price: number;
  max_price: number;
  min_price: number;
  closed_price: number;
  volume: number;
}

export interface OrderBook {
  slug: string;
  sell_min: number | null;
  sell_p25: number | null;
  sell_median: number | null;
  buy_max: number | null;
  spread: number | null;
  n_sell_live: number;
  n_buy_live: number;
  n_sell_total: number;
  n_buy_total: number;
}

/** Full URL for an item thumbnail from its stored relative path (null-safe).
    Only accepts a plain relative path so a malformed value can't redirect the <img> to
    an arbitrary host. */
export const thumbUrl = (thumb: string | null | undefined): string | null => {
  if (!thumb || thumb.startsWith("/") || thumb.includes("..") || thumb.includes("://")) {
    return null;
  }
  return `https://warframe.market/static/assets/${thumb}`;
};

/** Canonical warframe.market links for a slug (slug encoded for safe URLs). */
export const wfm = {
  item: (slug: string) => `https://warframe.market/items/${encodeURIComponent(slug)}`,
  rivenAuctions: (weaponSlug: string) =>
    `https://warframe.market/auctions/search?type=riven&weapon_url_name=${encodeURIComponent(weaponSlug)}`,
};

export interface OpportunityBacktest {
  horizon_days: number;
  dip_pct: number;
  observations: number;
  base_median_return: number | null;
  signals: number;
  signal_median_return: number | null;
  signal_hit_rate: number | null;
  median_gap_closed: number | null;
  edge: number | null;
}

export interface DispositionBacktest {
  total_changes: number;
  called: number;
  correct: number;
  hit_rate: number | null;
  base_rate: number | null;
  buff_share: number | null;
  calibration: { bucket: string; n: number; hit_rate: number | null }[];
}

export interface SetArbitrage {
  slug: string;
  name: string | null;
  set_price: number;
  parts_cost: number;
  n_parts: number;
  direction: "build" | "split";
  profit: number;
  margin_pct: number;
}

export interface DucatDeal {
  slug: string;
  name: string | null;
  thumb: string | null;
  ducats: number;
  price: number;
  ducats_per_plat: number;
}

export interface Trade {
  id: number;
  slug: string;
  side: "buy" | "sell";
  quantity: number;
  price: number;
  traded_at: string;
  note: string | null;
}

export interface Position {
  slug: string;
  quantity: number;
  avg_cost: number;
  price: number | null;
  unrealized: number | null;
}

export interface JournalSummary {
  realized_pnl: number;
  unrealized_pnl: number | null;
  total_pnl: number | null;
  n_trades: number;
  n_buys: number;
  n_sells: number;
  realized_by_slug: Record<string, number>;
  open_positions: Position[];
}

export interface NewTrade {
  slug: string;
  side: "buy" | "sell";
  quantity: number;
  price: number;
  note?: string | null;
}

export interface Digest {
  opportunities: Opportunity[];
  riven_deals: RivenDeal[];
  disposition_forecasts: DispositionForecast[];
  resurgence: { status: ResurgenceStatus; best_buys: ResurgenceImpact[] } | null;
  void_trader: VoidTraderStatus | null;
}

export const api = {
  summary: () => get<Summary>("/summary"),
  digest: () => get<Digest>("/digest"),
  volumeLeaderboard: (limit = 20) =>
    get<{ items: VolumeRow[] }>(`/leaderboard/volume?limit=${limit}`),
  opportunities: (minMarginPct = 0.05) =>
    get<{ count: number; opportunities: Opportunity[] }>(
      `/signals/opportunities?limit=50&min_margin_pct=${minMarginPct}`,
    ),
  rivenDeals: (positivesOnly = true, minComparables = 4, minDiscount = 0.25) =>
    get<{ count: number; deals: RivenDeal[] }>(
      `/signals/riven-deals?limit=50&positives_only=${positivesOnly}` +
        `&min_comparables=${minComparables}&min_discount=${minDiscount}`,
    ),
  dispositionChanges: () =>
    get<{ count: number; changes: DispositionChange[] }>("/signals/disposition-changes"),
  dispositionForecast: (direction?: "buff" | "nerf") =>
    get<{ count: number; forecasts: DispositionForecast[] }>(
      `/signals/disposition-forecast?limit=60${direction ? `&direction=${direction}` : ""}`,
    ),
  opportunityBacktest: () => get<OpportunityBacktest>("/signals/opportunity-backtest"),
  dispositionBacktest: () => get<DispositionBacktest>("/signals/disposition-backtest?cases=0"),
  setArbitrage: () =>
    get<{ count: number; deals: SetArbitrage[] }>("/signals/set-arbitrage?limit=100"),
  ducats: () => get<{ count: number; items: DucatDeal[] }>("/signals/ducats?limit=150"),
  voidTrader: () =>
    get<{ status: VoidTraderStatus; inventory: VoidTraderItem[] }>("/catalysts/void-trader"),
  resurgence: () =>
    get<{ status: ResurgenceStatus; inventory: ResurgenceItem[]; impact: ResurgenceImpact[] }>(
      "/catalysts/resurgence",
    ),
  itemPrices: (slug: string) =>
    get<{ slug: string; name: string | null; thumb: string | null; series: PriceBar[] }>(
      `/items/${encodeURIComponent(slug)}/prices`,
    ),
  orderbook: (slug: string) => get<OrderBook>(`/items/${encodeURIComponent(slug)}/orderbook`),
  search: (q: string) =>
    get<{ results: ItemSearchResult[] }>(`/items/search?q=${encodeURIComponent(q)}&limit=12`),
  journal: () => get<{ summary: JournalSummary; trades: Trade[] }>("/journal"),
  addTrade: (t: NewTrade) => send<{ id: number }>("/trades", "POST", t),
  deleteTrade: (id: number) => send<{ deleted: number }>(`/trades/${id}`, "DELETE"),
};
