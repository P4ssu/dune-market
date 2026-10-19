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
    avg: int | None
    cheapest: int | None
    trend_pct: float | None
    listing_count: int | None
    updated_at: datetime
    contributor: str
    stale: bool
