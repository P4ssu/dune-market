"""Scan Exchange screens and store prices."""

import logging
from collections.abc import Callable
from datetime import datetime

from PIL import Image, ImageChops, ImageStat

from dune_market.capture import grab_frame
from dune_market.models import ItemKey, Observation, Screen, Word
from dune_market.ocr import read_words
from dune_market.parse_buy import parse_buy
from dune_market.parse_sell import parse_sell
from dune_market.screens import classify
from dune_market.store import PriceStore

log = logging.getLogger(__name__)

JUMP_FACTOR = 5  # an average that changes by more than this factor is held back as a likely misread
_CHANGE_THRESHOLD = 1.0  # mean grey-level difference between thumbnails that counts as "new screen"
_THUMB_SIZE = (64, 40)


def observations_from_words(words: list[Word], contributor: str, now: datetime) -> list[Observation]:
    """Observations from one OCR'd frame; empty unless the Sell or Buy tab is open."""
    screen = classify(words)
    if screen == Screen.SELL:
        return [
            Observation(ItemKey(r.name, r.category, "unknown"), "sell", now, contributor,
                        avg=r.avg_price, low=r.low_price)
            for r in parse_sell(words)
        ]
    if screen == Screen.BUY:
        grade, rows = parse_buy(words)
        grade = "unknown" if grade == "all" else grade
        return [
            Observation(ItemKey(r.name, r.category, grade), "buy", now, contributor,
                        price=r.price, expires_in_s=r.expires_in_s)
            for r in rows
        ]
    return []  # My Orders (own listings) and every other screen


def _within_jump(new: int | None, old: int | None) -> bool:
    if new is None or not old:
        return True
    return 1 / JUMP_FACTOR <= new / old <= JUMP_FACTOR


def accept(obs: Observation, previous: Observation | None) -> bool:
    """False when a sell average or low price jumps implausibly against the stored one (likely OCR misread)."""
    if previous is None:
        return True
    return _within_jump(obs.avg, previous.avg) and _within_jump(obs.low, previous.low)


class Scanner:
    def __init__(
        self,
        store: PriceStore,
        contributor: str,
        grab: Callable[[], Image.Image | None] = grab_frame,
        read: Callable[[Image.Image], list[Word]] = read_words,
    ):
        self._store = store
        self._contributor = contributor
        self._grab = grab
        self._read = read
        self._last_thumb: Image.Image | None = None
        self._held: dict[ItemKey, tuple[int | None, int | None]] = {}

    def _changed(self, frame: Image.Image) -> bool:
        thumb = frame.convert("L").resize(_THUMB_SIZE)
        previous, self._last_thumb = self._last_thumb, thumb
        if previous is None:
            return True
        return ImageStat.Stat(ImageChops.difference(thumb, previous)).mean[0] > _CHANGE_THRESHOLD

    def scan_once(self, now: datetime) -> int:
        """Scan the screen once; returns how many observations were stored."""
        try:
            frame = self._grab()
            if frame is None or not self._changed(frame):
                return 0
            observations = observations_from_words(self._read(frame), self._contributor, now)
            accepted = []
            for obs in observations:
                if obs.kind == "buy" or self._passes_guard(obs):
                    accepted.append(obs)
            if accepted:
                self._store.add(accepted)
            return len(accepted)
        except Exception:
            log.exception("scan failed")
            return 0

    def _passes_guard(self, obs: Observation) -> bool:
        if accept(obs, self._store.latest_sell(obs.key)):
            self._held.pop(obs.key, None)
            return True
        value = (obs.avg, obs.low)
        if self._held.get(obs.key) == value:  # the same odd value twice in a row is believed
            del self._held[obs.key]
            return True
        self._held[obs.key] = value
        return False
