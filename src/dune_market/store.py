"""The interface every price store implements (local SQLite, shared remote)."""

from datetime import datetime
from typing import Protocol

from dune_market.models import ItemKey, ItemStats, Observation


class PriceStore(Protocol):
    def add(self, observations: list[Observation]) -> None: ...

    def latest_sell(self, key: ItemKey) -> Observation | None: ...

    def lookup(self, name: str, category: str, now: datetime) -> list[ItemStats]:
        """One entry per grade, newest first; empty when the item is unknown."""
        ...
