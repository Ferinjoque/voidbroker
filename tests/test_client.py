from __future__ import annotations

import time

import httpx
import respx

from voidbroker.client import AsyncRateLimiter, WarframeMarketClient
from voidbroker.config import Settings


def _settings() -> Settings:
    return Settings(rate_limit=50.0, max_retries=2)


async def test_rate_limiter_spaces_requests():
    rl = AsyncRateLimiter(rate=20)  # 0.05s minimum interval
    start = time.monotonic()
    for _ in range(3):
        await rl.acquire()
    elapsed = time.monotonic() - start
    # First call is free; the next two each wait one interval (~0.1s total).
    assert elapsed >= 0.08


@respx.mock
async def test_get_items(sample_item_raw):
    respx.get("https://api.warframe.market/v2/items").mock(
        return_value=httpx.Response(200, json={"data": [sample_item_raw]})
    )
    async with WarframeMarketClient(_settings()) as client:
        items = await client.get_items()
    assert len(items) == 1
    assert items[0].slug == "secura_dual_cestra"


@respx.mock
async def test_get_statistics(sample_stat_rows):
    respx.get("https://api.warframe.market/v1/items/foo/statistics").mock(
        return_value=httpx.Response(
            200, json={"payload": {"statistics_closed": {"90days": sample_stat_rows}}}
        )
    )
    async with WarframeMarketClient(_settings()) as client:
        records = await client.get_statistics("foo")
    assert len(records) == 2
    assert records[0].volume == 137


@respx.mock
async def test_get_orders(sample_orders_raw):
    respx.get("https://api.warframe.market/v2/orders/item/foo").mock(
        return_value=httpx.Response(200, json={"data": sample_orders_raw})
    )
    async with WarframeMarketClient(_settings()) as client:
        orders = await client.get_orders("foo")
    assert len(orders) == 5
    assert orders[0].type == "sell"


@respx.mock
async def test_retries_then_succeeds(sample_item_raw):
    route = respx.get("https://api.warframe.market/v2/items").mock(
        side_effect=[
            httpx.Response(429, headers={"Retry-After": "0"}),  # rate-limited once
            httpx.Response(200, json={"data": [sample_item_raw]}),
        ]
    )
    async with WarframeMarketClient(_settings()) as client:
        items = await client.get_items()
    assert route.call_count == 2
    assert len(items) == 1
