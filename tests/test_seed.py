from __future__ import annotations

from voidbroker.ingest import seed_ingest
from voidbroker.models import (
    Item,
    ItemDetail,
    Order,
    RivenAttribute,
    RivenAuction,
    RivenWeapon,
    StatRecord,
)


def _item(slug: str, name: str) -> Item:
    raw = {
        "id": slug,
        "slug": slug,
        "tags": ["weapon"],
        "i18n": {"en": {"name": name, "thumb": "t.png"}},
    }
    return Item.from_api(raw, "en")


class SeedFakeClient:
    """No-network stand-in covering every call seed_ingest makes (worldstate excluded)."""

    class _S:
        platform = "pc"

    settings = _S()

    def __init__(self, items, weapons, stats, orders, attrs, auctions):
        self._items, self._weapons = items, weapons
        self._stats, self._orders, self._attrs, self._auctions = stats, orders, attrs, auctions

    async def get_items(self):
        return self._items

    async def get_riven_weapons(self):
        return self._weapons

    async def get_statistics(self, slug, window="90days"):
        return self._stats

    async def get_orders(self, slug):
        return self._orders

    async def get_item_detail(self, slug):
        return ItemDetail(slug=slug, ducats=15, tradable=True)

    async def get_riven_attributes(self):
        return self._attrs

    async def search_riven_auctions(self, weapon_slug, sort_by="price_asc"):
        return self._auctions


async def test_seed_ingest_curates_prime_items_only(
    storage, sample_weapon_raw, sample_stat_rows, sample_orders_raw,
    sample_riven_attr_raw, sample_auction_raw,
):
    client = SeedFakeClient(
        # one Prime item (selected) and one non-Prime (must be excluded by the filter)
        items=[
            _item("ash_prime_set", "Ash Prime Set"),
            _item("secura_dual_cestra", "Secura Dual Cestra"),
        ],
        weapons=[RivenWeapon.from_api(sample_weapon_raw, "en")],
        stats=[StatRecord.model_validate(r) for r in sample_stat_rows],
        orders=[Order.model_validate(o) for o in sample_orders_raw],
        attrs=[RivenAttribute.from_api(sample_riven_attr_raw, "en")],
        auctions=[RivenAuction.from_api(sample_auction_raw)],
    )

    report = await seed_ingest(client, storage, worldstate=False)

    assert report.items == 2  # whole catalog synced
    # but only the Prime item was ingested for prices/orders/details
    assert report.order_snapshots == 1
    assert report.detail_rows == 1
    assert report.price_rows > 0
    assert report.riven_auctions > 0

    priced = {r["slug"] for r in storage._rows("SELECT DISTINCT slug FROM price_history")}
    assert priced == {"ash_prime_set"}  # the non-Prime slug was filtered out
