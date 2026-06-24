"""Async, rate-limited HTTP client for the warframe.market API (v1 + v2).

The free API asks callers to stay around 3 requests/second. ``AsyncRateLimiter``
enforces a global minimum interval between requests so a full-catalog sweep stays
polite, and the client retries transient failures with backoff (honoring Retry-After).
"""

from __future__ import annotations

import asyncio
import time
from urllib.parse import quote

import httpx

from .config import WFM_V1_BASE, WFM_V2_BASE, Settings, get_settings
from .models import (
    Item,
    ItemDetail,
    Order,
    RivenAttribute,
    RivenAuction,
    RivenWeapon,
    StatRecord,
)

# Status codes worth retrying: rate limit + transient server errors.
_RETRYABLE = {429, 500, 502, 503, 504}


class AsyncRateLimiter:
    """Spaces out calls so we issue at most ``rate`` requests per second, globally."""

    def __init__(self, rate: float) -> None:
        self._min_interval = 1.0 / rate
        self._lock = asyncio.Lock()
        self._next_allowed = 0.0

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                await asyncio.sleep(wait)
            self._next_allowed = max(now, self._next_allowed) + self._min_interval


class WarframeMarketClient:
    """Typed access to the warframe.market endpoints voidbroker ingests."""

    def __init__(self, settings: Settings | None = None, client: httpx.AsyncClient | None = None):
        self.settings = settings or get_settings()
        self._limiter = AsyncRateLimiter(self.settings.rate_limit)
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=self.settings.request_timeout,
            headers=self._default_headers(),
        )

    def _default_headers(self) -> dict[str, str]:
        return {
            "accept": "application/json",
            "Platform": self.settings.platform,
            "Language": self.settings.language,
            "Crossplay": "true" if self.settings.crossplay else "false",
            "User-Agent": "voidbroker/0.1 (+local research client)",
            **self.settings.auth_header,
        }

    async def __aenter__(self) -> WarframeMarketClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get(self, url: str, params: dict | None = None) -> dict:
        last_exc: Exception | None = None
        for attempt in range(self.settings.max_retries + 1):
            await self._limiter.acquire()
            try:
                resp = await self._client.get(
                    url, params=params, headers=self._default_headers()
                )
            except httpx.HTTPError as exc:  # network-level failure
                last_exc = exc
                await asyncio.sleep(2**attempt)
                continue
            if resp.status_code in _RETRYABLE and attempt < self.settings.max_retries:
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2**attempt
                await asyncio.sleep(delay)
                continue
            resp.raise_for_status()
            return resp.json()
        raise RuntimeError(f"GET {url} failed after retries") from last_exc

    # --- catalog -----------------------------------------------------------------

    async def get_items(self) -> list[Item]:
        data = await self._get(f"{WFM_V2_BASE}/items")
        return [Item.from_api(raw, self.settings.language) for raw in data.get("data", [])]

    async def get_item_detail(self, slug: str) -> ItemDetail:
        """Per-item detail (ducats, set composition, trading tax) from v2 /item/{slug}."""
        data = await self._get(f"{WFM_V2_BASE}/item/{quote(slug, safe='')}")
        return ItemDetail.from_api(data["data"])

    async def get_riven_weapons(self) -> list[RivenWeapon]:
        data = await self._get(f"{WFM_V2_BASE}/riven/weapons")
        return [RivenWeapon.from_api(raw, self.settings.language) for raw in data.get("data", [])]

    async def get_riven_attributes(self) -> list[RivenAttribute]:
        data = await self._get(f"{WFM_V2_BASE}/riven/attributes")
        return [
            RivenAttribute.from_api(raw, self.settings.language) for raw in data.get("data", [])
        ]

    async def search_riven_auctions(
        self, weapon_slug: str, sort_by: str = "price_asc"
    ) -> list[RivenAuction]:
        data = await self._get(
            f"{WFM_V1_BASE}/auctions/search",
            params={"type": "riven", "weapon_url_name": weapon_slug, "sort_by": sort_by},
        )
        auctions = data.get("payload", {}).get("auctions", [])
        return [RivenAuction.from_api(a) for a in auctions]

    # --- market data -------------------------------------------------------------

    async def get_statistics(self, slug: str, window: str = "90days") -> list[StatRecord]:
        """Daily (``90days``) or hourly (``48hours``) price history for one item."""
        data = await self._get(f"{WFM_V1_BASE}/items/{quote(slug, safe='')}/statistics")
        rows = data.get("payload", {}).get("statistics_closed", {}).get(window, [])
        return [StatRecord.model_validate(r) for r in rows]

    async def get_orders(self, slug: str) -> list[Order]:
        data = await self._get(f"{WFM_V2_BASE}/orders/item/{quote(slug, safe='')}")
        return [Order.model_validate(o) for o in data.get("data", [])]
