# Warframe Market API, voidbroker reference

> **Upstream:** the official docs (server v0.23.0) are captured in
> [`official-doc.md`](official-doc.md), rendered from the
> [WFM Api v2 Documentation (Notion)](https://42bytes.notion.site/WFM-Api-v2-Documentation-5d987e4aa2f74b55a80db1a09932459d)
> via a headless browser. **This file is the source of truth for how voidbroker uses the
> API**, every shape below was verified against the live API on 2026-06-22.

## Base URLs

The API spans two generations. **v2 is current** for catalog/orders; **statistics still
lives on v1**. voidbroker talks to both.

| Generation | Base URL |
|------------|----------|
| v1 | `https://api.warframe.market/v1` |
| v2 | `https://api.warframe.market/v2` |

## Authentication

- **Read endpoints are public**, `items`, `riven/weapons`, `orders`, `statistics`
  need no token. voidbroker's ingestion is entirely unauthenticated.
- Authenticated actions use **v2 OAuth2 Bearer** tokens: `Authorization: Bearer <token>`
  (legacy v1 tokens used the `JWT ` prefix and have scope `all`). voidbroker only sends this
  if `VOIDBROKER_WFM_TOKEN` is set, and uses the Bearer form.

## Headers

| Header | Value | Notes |
|--------|-------|-------|
| `accept` | `application/json` | |
| `Platform` | `pc` \| `ps4` \| `xbox` \| `switch` \| `mobile` | Selects the trading platform's market |
| `Language` | `en`, `ru`, … (14 total) | Selects the language block returned under `i18n` |
| `Crossplay` | `true` \| `false` | Include cross-play orders from other platforms (default false) |

## Rate limit

Stay around **3 requests/second**. Also cap *concurrency*: too many simultaneous connections
from one IP returns `509` (distinct from the `429` rate-limit + Cloudflare challenge).
voidbroker enforces a global minimum interval (`AsyncRateLimiter`), bounds fan-out with a
semaphore, and retries `429`/`5xx` with backoff, honoring `Retry-After`.

## Cheaper order endpoints (not yet wired)

Two lighter alternatives to the full per-item order book, worth adopting later:

- `GET /v2/orders/recent`, up to 500 orders from the last 4h, online users only. A single
  call for a market-wide "tape" of what's actively moving.
- `GET /v2/orders/item/{slug}/top`, top ≤5 buy + ≤5 sell from online users, with `rank` /
  `subtype` query params. Far cheaper than the full book when only the best quotes matter.

## Response envelopes

- **v2:** `{ "apiVersion": "...", "data": <payload>, "error": null }`
- **v1:** `{ "payload": { ... } }`

On error, v2 sets `error` and may omit `data`; v1 returns `{ "error": { ... } }`.

---

## Endpoints voidbroker ingests

### `GET /v2/items`, full item catalog

~3834 items. One object each:

```json
{
  "id": "54aae292e7798909064f1575",
  "slug": "secura_dual_cestra",
  "gameRef": "/Lotus/Weapons/Syndicates/PerrinSequence/Pistols/PSDualCestra",
  "tags": ["syndicate", "weapon", "secondary"],
  "i18n": { "en": { "name": "Secura Dual Cestra", "icon": "...png", "thumb": "...png" } }
}
```

- `slug` is the stable key used in every other item endpoint.
- Riven mods carry the `"riven"` tag (voidbroker's `Item.is_riven`).

### `GET /v2/riven/weapons`, riven-capable weapons (carries disposition)

~417 weapons. **`disposition` is included here**, snapshotting this endpoint over time
is what builds voidbroker's disposition-history dataset.

```json
{
  "id": "5c5ca81696e8d2003834fdcc",
  "slug": "kulstar",
  "gameRef": "/Lotus/Weapons/Grineer/Pistols/GrnTorpedoPistol/GrnTorpedoPistol",
  "group": "secondary",
  "rivenType": "pistol",
  "disposition": 1.3,
  "reqMasteryRank": 5,
  "i18n": { "en": { "name": "Kulstar", "icon": "...", "thumb": "..." } }
}
```

### `GET /v1/items/{slug}/statistics`, price history (candlestick-grade)

Returns `payload.statistics_closed` with two windows: **`48hours`** (hourly) and
**`90days`** (daily). Each row is a full OHLC candle plus volume and indicators:

```json
{
  "datetime": "2026-06-21T00:00:00.000+00:00",
  "volume": 134,
  "min_price": 78, "max_price": 90,
  "open_price": 80, "closed_price": 88,
  "avg_price": 84, "wa_price": 86.149, "median": 87,
  "moving_avg": 86.4,
  "donch_top": 95, "donch_bot": 78,
  "id": "6a387cd515830c001257f733"
}
```

There is also a `statistics_live` block (omitted by voidbroker for now). `wa_price` is the
volume-weighted average; `donch_top`/`donch_bot` are Donchian channel bounds.

### `GET /v2/orders/item/{slug}`, live order book

Every standing buy/sell order for an item. The author's `status` is the key liquidity
signal, voidbroker treats only `online`/`ingame` orders as fillable ("live").

```json
{
  "id": "5a3c9ee028edde0e6c580caf",
  "type": "sell",
  "platinum": 99,
  "quantity": 1,
  "perTrade": 1,
  "visible": true,
  "createdAt": "2017-12-22T05:57:52Z",
  "updatedAt": "2026-04-16T08:30:35Z",
  "itemId": "5a2feeb2c2c9e90cbdaa23d3",
  "user": {
    "id": "5627080eb66f83150b203df3",
    "ingameName": "Nadarejin",
    "reputation": 38,
    "platform": "pc",
    "status": "offline",
    "lastSeen": "2026-06-22T13:27:22Z"
  }
}
```

---

## Deprecations confirmed (corrections to stale docs)

These **v1** endpoints are dead, call them and you get an error, not data:

| Endpoint | Result | Replacement |
|----------|--------|-------------|
| `GET /v1/items` | `{ "error": ... }` | `GET /v2/items` |
| `GET /v1/items/{slug}/orders` | `"Deprecated"` | `GET /v2/orders/item/{slug}` |

`GET /v1/items/{slug}/statistics` is **still live** and is the only statistics source.

## Not yet verified (Phase 2, riven valuation)

These power the riven fair-value model and aren't wired into ingestion yet; verify shapes
before relying on them:

- `GET /v1/auctions/search?type=riven&weapon_url_name=<slug>&...`, note this expects the
  weapon's **auction** url_name (e.g. `kuva_bramma`, not `bramma`); a bad slug returns
  `app.auctions.errors.item_not_exist`.
- `GET /v2/riven/attributes`, the riven stat catalog (positives/negatives) for appraisal.
