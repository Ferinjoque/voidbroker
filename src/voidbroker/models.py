"""Pydantic models mirroring the warframe.market API, plus storage-facing snapshots.

The API mixes camelCase (v2) and snake_case (v1) and nests localized strings under
``i18n``. These models normalize everything to snake_case Python attributes so the rest
of the codebase never deals with raw API quirks.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _resolve_i18n(i18n: dict[str, Any], language: str, key: str = "name") -> str | None:
    """Pull a localized field, falling back to English then any available language."""
    for lang in (language, "en", *i18n.keys()):
        block = i18n.get(lang)
        if block and block.get(key):
            return block[key]
    return None


class Item(BaseModel):
    """A tradable item from the v2 ``/items`` catalog."""

    id: str
    slug: str
    game_ref: str | None = None
    tags: list[str] = Field(default_factory=list)
    name: str | None = None
    thumb: str | None = None  # relative CDN path under warframe.market/static/assets/

    @classmethod
    def from_api(cls, raw: dict[str, Any], language: str) -> Item:
        i18n = raw.get("i18n", {})
        return cls(
            id=raw["id"],
            slug=raw["slug"],
            game_ref=raw.get("gameRef"),
            tags=raw.get("tags", []),
            name=_resolve_i18n(i18n, language),
            thumb=_resolve_i18n(i18n, language, key="thumb"),
        )

    @property
    def is_riven(self) -> bool:
        return "riven" in self.tags


class ItemDetail(BaseModel):
    """Per-item detail from v2 ``/item/{slug}``, ducats + set composition.

    The catalog list endpoint omits these, so they're fetched per item. ``set_parts`` holds
    the item *ids* of a set's components (resolve to slugs via the items table).
    """

    slug: str
    ducats: int = 0
    trading_tax: int = 0
    set_root: bool = False  # this item is the assembled set
    set_parts: list[str] = Field(default_factory=list)  # component item ids
    tradable: bool = True

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> ItemDetail:
        return cls(
            slug=raw["slug"],
            ducats=raw.get("ducats") or 0,
            trading_tax=raw.get("tradingTax") or 0,
            set_root=bool(raw.get("setRoot", False)),
            set_parts=list(raw.get("setParts") or []),
            tradable=bool(raw.get("tradable", True)),
        )


class RivenWeapon(BaseModel):
    """A riven-capable weapon from v2 ``/riven/weapons``, carries live disposition.

    Snapshotting this over time is the dataset the disposition predictor trains on.
    """

    id: str
    slug: str
    game_ref: str | None = None
    group: str | None = None
    riven_type: str | None = None
    disposition: float | None = None
    req_mastery_rank: int | None = None
    name: str | None = None

    @classmethod
    def from_api(cls, raw: dict[str, Any], language: str) -> RivenWeapon:
        return cls(
            id=raw["id"],
            slug=raw["slug"],
            game_ref=raw.get("gameRef"),
            group=raw.get("group"),
            riven_type=raw.get("rivenType"),
            disposition=raw.get("disposition"),
            req_mastery_rank=raw.get("reqMasteryRank"),
            name=_resolve_i18n(raw.get("i18n", {}), language),
        )


class RivenAttribute(BaseModel):
    """A riven stat from v2 ``/riven/attributes`` (the appraisal feature vocabulary)."""

    id: str
    slug: str
    group: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    name: str | None = None

    @classmethod
    def from_api(cls, raw: dict[str, Any], language: str) -> RivenAttribute:
        return cls(
            id=raw["id"],
            slug=raw["slug"],
            group=raw.get("group"),
            prefix=raw.get("prefix"),
            suffix=raw.get("suffix"),
            name=_resolve_i18n(raw.get("i18n", {}), language),
        )


class RivenStat(BaseModel):
    """One rolled stat on a riven: which attribute, its value, and its sign."""

    url_name: str
    value: float
    positive: bool


class RivenAuction(BaseModel):
    """A live riven auction from v1 ``/auctions/search`` (flattened owner + item)."""

    id: str
    weapon_url_name: str
    riven_name: str | None = None
    starting_price: float | None = None
    buyout_price: float | None = None
    top_bid: float | None = None
    is_direct_sell: bool = False
    visible: bool = True
    closed: bool = False
    re_rolls: int = 0
    mod_rank: int = 0
    mastery_level: int | None = None
    polarity: str | None = None
    owner_status: str = "offline"
    owner_reputation: int = 0
    attributes: list[RivenStat] = Field(default_factory=list)

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> RivenAuction:
        item = raw.get("item", {})
        owner = raw.get("owner", {})
        return cls(
            id=raw["id"],
            weapon_url_name=item.get("weapon_url_name", ""),
            riven_name=item.get("name"),
            starting_price=raw.get("starting_price"),
            buyout_price=raw.get("buyout_price"),
            top_bid=raw.get("top_bid"),
            is_direct_sell=raw.get("is_direct_sell", False),
            visible=raw.get("visible", True),
            closed=raw.get("closed", False),
            re_rolls=item.get("re_rolls", 0),
            mod_rank=item.get("mod_rank", 0),
            mastery_level=item.get("mastery_level"),
            polarity=item.get("polarity"),
            owner_status=owner.get("status", "offline"),
            owner_reputation=owner.get("reputation", 0),
            attributes=[RivenStat(**a) for a in item.get("attributes", [])],
        )

    @property
    def is_live(self) -> bool:
        return (
            self.visible
            and not self.closed
            and self.owner_status in {"online", "ingame"}
        )


class StatRecord(BaseModel):
    """One row of daily/hourly price history from v1 ``/statistics`` (candlestick-grade)."""

    model_config = ConfigDict(populate_by_name=True)

    datetime: datetime
    volume: int
    min_price: float
    max_price: float
    open_price: float
    closed_price: float
    avg_price: float
    wa_price: float | None = None
    median: float | None = None
    moving_avg: float | None = None
    donch_top: float | None = None
    donch_bot: float | None = None


class OrderUser(BaseModel):
    """Order author, ``status`` (online/ingame/offline) drives liquidity scoring."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    ingame_name: str | None = Field(default=None, alias="ingameName")
    reputation: int = 0
    status: str = "offline"
    platform: str | None = None


class Order(BaseModel):
    """A live buy/sell order from v2 ``/orders/item/{slug}``."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    type: str  # "buy" | "sell"
    platinum: float
    quantity: int
    per_trade: int = Field(default=1, alias="perTrade")
    visible: bool = True
    created_at: datetime | None = Field(default=None, alias="createdAt")
    updated_at: datetime | None = Field(default=None, alias="updatedAt")
    user: OrderUser | None = None

    @property
    def is_live(self) -> bool:
        """A standing, visible order from a reachable seller/buyer."""
        return self.visible and self.user is not None and self.user.status in {"online", "ingame"}
