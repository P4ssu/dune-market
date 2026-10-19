"""Scan Exchange screens and store prices."""

import logging
import time
from collections.abc import Callable
from datetime import datetime

from PIL import Image, ImageChops, ImageStat

from dune_market.capture import grab_frame
from dune_market.models import ItemKey, Observation, Screen, Word
from dune_market.ocr import name_key, read_words
from dune_market.parse_buy import parse_buy
from dune_market.parse_sell import parse_sell
from dune_market.screens import classify, exchange_tab_open
from dune_market.store import PriceStore

log = logging.getLogger(__name__)

JUMP_FACTOR = 5  # an average that changes by more than this factor is held back as a likely misread
_CHANGE_THRESHOLD = 1.0  # mean grey-level difference between thumbnails that counts as "new screen"
_THUMB_SIZE = (64, 40)
_NOT_EXCHANGE_RECHECK_S = 1.0  # after "no Exchange tab", look again no sooner than this
# Frame fractions (left, top, right, bottom). The list area is read on every scan; the top strip with
# the character name and Solari balance and the bottom bar are never read (also faster). On the Sell
# tab the detail panel title (name and grade badge of the selected row) is read in a second, tight crop.
SCAN_REGION = (0.03, 0.19, 0.71, 0.83)
PANEL_TITLE_REGION = (0.70, 0.14, 0.97, 0.22)


def observations_from_words(words: list[Word], contributor: str, now: datetime) -> list[Observation]:
    """Observations from one OCR'd frame; empty unless the Sell or Buy tab is open."""
    screen = classify(words)
    if screen == Screen.SELL:
        return [
            Observation(ItemKey(r.name, r.category, r.grade or "unknown"), "sell", now, contributor,
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
        read: Callable[[Image.Image, tuple[int, int]], list[Word]] = read_words,
        active: Callable[[], bool] = lambda: True,
    ):
        self._store = store
        self._contributor = contributor
        self._grab = grab
        self._read = read
        self._active = active
        self._recheck_at = 0.0
        self._last_thumb: Image.Image | None = None
        self._held: dict[ItemKey, tuple[int | None, int | None]] = {}
        self._seen: set[tuple[str, str, str]] = set()
        self.last_new = 0  # items not seen before in this session, in the last scan
        self.session_total = 0  # distinct items seen in this session

    def _changed(self, frame: Image.Image) -> bool:
        thumb = frame.convert("L").resize(_THUMB_SIZE)
        previous, self._last_thumb = self._last_thumb, thumb
        if previous is None:
            return True
        return ImageStat.Stat(ImageChops.difference(thumb, previous)).mean[0] > _CHANGE_THRESHOLD

    def scan_once(self, now: datetime) -> int:
        """Scan the screen once; returns how many observations were stored."""
        try:
            if not self._active():
                return 0  # the game is not in front: do no work at all
            frame = self._grab()
            if frame is None or not self._changed(frame):
                return 0
            # Reading the whole list costs about a second of CPU, so first look at the small tab bar strip.
            if time.monotonic() < self._recheck_at:
                return 0
            if not exchange_tab_open(frame, self._read):
                self._recheck_at = time.monotonic() + _NOT_EXCHANGE_RECHECK_S
                return 0
            width, height = frame.size
            left, top = int(width * SCAN_REGION[0]), int(height * SCAN_REGION[1])
            region = frame.crop((left, top, int(width * SCAN_REGION[2]), int(height * SCAN_REGION[3])))
            words = self._read(region, (left, top))
            if classify(words) == Screen.SELL:
                words = words + self._read_panel_title(frame)
            observations = observations_from_words(words, self._contributor, now)
            accepted = []
            for obs in observations:
                if obs.kind == "buy" or self._passes_guard(obs):
                    accepted.append(obs)
            if accepted:
                self._store.add(accepted)
            keys = {(name_key(o.key.name), o.key.category, o.key.grade) for o in accepted}
            self.last_new = len(keys - self._seen)
            self._seen |= keys
            self.session_total = len(self._seen)
            return len(accepted)
        except Exception:
            log.exception("scan failed")
            return 0

    def _read_panel_title(self, frame: Image.Image) -> list[Word]:
        width, height = frame.size
        left, top = int(width * PANEL_TITLE_REGION[0]), int(height * PANEL_TITLE_REGION[1])
        crop = frame.crop((left, top, int(width * PANEL_TITLE_REGION[2]), int(height * PANEL_TITLE_REGION[3])))
        return [w for w in self._read(crop, (left, top)) if w.x >= left]

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
