"""Dataclasses and enums shared by all modules."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Literal


@dataclass(frozen=True)
class Word:
    """A span of OCR text with its top-left pixel box.

    The OCR engine returns line-level spans, so `text` may hold several words.
    """

    text: str
    x: float
    y: float
    w: float
    h: float


class Screen(Enum):
    SELL = "sell"
    BUY = "buy"
    MY_ORDERS = "my_orders"
    OTHER = "other"


@dataclass(frozen=True)
class SellRow:
    category: str
    name: str
    quantity: int | None  # dim column the OCR often misses
    avg_price: int
    low_price: int
    grade: str | None = None  # only known for the row selected in the detail panel


@dataclass(frozen=True)
class BuyRow:
    category: str
    name: str
    price: int
    expires_in_s: int


@dataclass(frozen=True)
class ItemKey:
    name: str
    category: str
    grade: str  # "unknown" when scanned with GRADE: ALL


@dataclass(frozen=True)
class Observation:
    key: ItemKey
    kind: Literal["sell", "buy"]
    observed_at: datetime
    contributor: str
    avg: int | None = None
    low: int | None = None
    price: int | None = None
    expires_in_s: int | None = None


@dataclass(frozen=True)
class ItemStats:
    key: ItemKey
    lowest: int | None  # cheapest listing in the newest scan session (Sell tab LOW or Buy tab)
    highest: int | None  # last known most expensive listing seen on the Buy tab
    trend_pct: float | None  # change of the Sell tab low price
    listing_count: int | None
    updated_at: datetime
    contributor: str
    stale: bool
    avg: int | None = None  # the game's average price from the newest Sell tab scan, however old
    avg_at: datetime | None = None  # when that scan was made
    avg_from_listings: bool = False  # no Sell scan: `avg` is the mean of the Buy tab listings seen instead
    all_time_low: int | None = None  # the cheapest price ever seen for this item key
    all_time_low_at: datetime | None = None
