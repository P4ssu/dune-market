"""Scan Exchange screens and store prices."""

import logging
import statistics
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime

import numpy as np
from PIL import Image

from dune_market.capture import grab_frame
from dune_market.models import ItemKey, Observation, Screen, Word
from dune_market.ocr import name_key, read_header, read_words
from dune_market.parse_buy import parse_buy
from dune_market.parse_sell import parse_sell
from dune_market.layout import content_box, region
from dune_market.screens import MIN_GOLD, bar_scores, classify, exchange_tab_open
from dune_market.store import PriceStore

log = logging.getLogger(__name__)

JUMP_FACTOR = 5  # an average that changes by more than this factor is held back as a likely misread
_GUARD_HISTORY = 5  # the guard compares against the median of this many stored Sell scans
# Change detection on a small grey copy of the list area: a pixel counts as changed when its grey level moves
# by more than _PIXEL_STEP, and the list counts as changed when more than _CHANGE_SHARE of its pixels did.
# Measured on screenshots: one row appearing or vanishing changes about 0.007, prices changing in place
# about 0.011, another tab about 0.2; a whole-screen mean (the old check) missed the first two.
_THUMB_SIZE = (240, 150)
_PIXEL_STEP = 24
_CHANGE_SHARE = 0.002
_MAX_RECHECKS = 2  # extra reads of an unchanged list after a price was held back
_SCAN_DELAY_S = 0.1  # between scans while the Exchange is open
_IDLE_DELAY_S = 0.5  # between checks while it is not
_EXCHANGE_RECENT_S = 3.0  # how long after the last Exchange frame the quick pace is kept
# Fractions of the picture (left, top, right, bottom), measured inside the black bars. The list area is read on every scan; the top strip with
# the character name and Solari balance and the bottom bar are never read (also faster). On the Sell
# tab the detail panel title (name and grade badge of the selected row) is read in a second, tight crop.
SCAN_REGION = (0.03, 0.156, 0.71, 0.867)
PANEL_TITLE_REGION = (0.70, 0.09, 0.97, 0.19)


def buy_tab_on_all_grades(words: list[Word]) -> bool:
    """True for a Buy tab list filtered on GRADE: ALL (or with an unreadable grade label)."""
    if classify(words) != Screen.BUY:
        return False
    grade, rows = parse_buy(words)
    return grade == "all" and bool(rows)


def observations_from_words(words: list[Word], contributor: str, now: datetime) -> list[Observation]:
    """Observations from one OCR'd frame; empty unless the Sell or Buy tab is open.

    A Buy tab on GRADE: ALL gives nothing: its rows mix grades, so a price cannot be filed under one.
    """
    screen = classify(words)
    if screen == Screen.SELL:
        return [
            Observation(ItemKey(r.name, r.category, r.grade or "unknown"), "sell", now, contributor,
                        avg=r.avg_price, low=r.low_price)
            for r in parse_sell(words)
        ]
    if screen == Screen.BUY:
        grade, rows = parse_buy(words)
        if grade == "all":
            return []
        return [
            Observation(ItemKey(r.name, r.category, grade), "buy", now, contributor,
                        price=r.price, expires_in_s=r.expires_in_s)
            for r in rows
        ]
    return []  # My Orders (own listings) and every other screen


def _describe(obs: Observation) -> str:
    if obs.kind == "sell":
        return "Sell tab"
    return f"Buy tab · {obs.key.category} · grade {obs.key.grade}"


def _within_jump(new: int | None, old: int | None) -> bool:
    if new is None or not old:
        return True
    return 1 / JUMP_FACTOR <= new / old <= JUMP_FACTOR


def accept(obs: Observation, previous: Observation | None) -> bool:
    """False when a sell average or low price jumps implausibly against the stored one (likely OCR misread)."""
    if previous is None:
        return True
    return _within_jump(obs.avg, previous.avg) and _within_jump(obs.low, previous.low)


def typical_sell(sells: list[Observation]) -> Observation | None:
    """The median of recent Sell scans, so one stored misread does not block every correct value after it."""
    if not sells:
        return None

    def median(values: list[int | None]) -> int | None:
        known = [v for v in values if v]
        return int(statistics.median(known)) if known else None

    return replace(sells[0], avg=median([s.avg for s in sells]), low=median([s.low for s in sells]))


class Scanner:
    def __init__(
        self,
        store: PriceStore,
        contributor: str,
        grab: Callable[[], Image.Image | None] = grab_frame,
        read: Callable[[Image.Image, tuple[int, int]], list[Word]] = read_words,
        active: Callable[[], bool] = lambda: True,
        exchange_open: Callable[[Image.Image], bool] = exchange_tab_open,
    ):
        self._store = store
        self._contributor = contributor
        self._grab = grab
        self._read = read
        self._active = active
        self._exchange_open = exchange_open
        self._exchange_seen_at = float("-inf")
        self._last_frame: Image.Image | None = None
        self._last_thumb: np.ndarray | None = None  # the previous frame's list area
        self._read_thumb: np.ndarray | None = None  # the list area as it was when last read
        self._rechecks = 0  # reads still owed to held-back prices
        self._held: dict[ItemKey, tuple[int | None, int | None]] = {}
        self._seen: set[tuple[str, str, str]] = set()
        self.last_new = 0  # items not seen before in this session, in the last scan
        self.session_total = 0  # distinct items seen in this session
        self.last_label = ""  # what the last scan read, e.g. "Buy tab · GARMENTS - LIGHTARMOR · grade 3"
        self.last_rows = 0
        self.skipped_all_grades = False  # the last read was a Buy tab on GRADE: ALL, so nothing was saved

    def explain(self) -> str:
        """Why the last frame was not taken for the Exchange (for --debug and bug reports)."""
        frame = self._last_frame
        if frame is None:
            return "no frame seen yet"
        q, e = bar_scores(frame)
        return (f"frame {frame.width}x{frame.height}, picture area {content_box(frame)}, "
                f"key box gold {q:.2f}/{e:.2f} (needs {MIN_GOLD:.2f}+ on both)")

    @property
    def idle_delay(self) -> float:
        """Seconds to wait between scans: quick while the Exchange is open, relaxed otherwise."""
        return _SCAN_DELAY_S if time.monotonic() - self._exchange_seen_at < _EXCHANGE_RECENT_S else _IDLE_DELAY_S

    @staticmethod
    def _thumb(frame: Image.Image, box: tuple[int, int, int, int]) -> np.ndarray:
        return np.asarray(frame.crop(box).convert("L").resize(_THUMB_SIZE), dtype=np.int16)

    @staticmethod
    def _differs(a: np.ndarray | None, b: np.ndarray | None) -> bool:
        if a is None or b is None:
            return True
        return float((np.abs(a - b) > _PIXEL_STEP).mean()) > _CHANGE_SHARE

    def scan_once(self, now: datetime) -> int:
        """Scan the screen once; returns how many observations were stored.

        The list is read once it has stopped moving (scrolling, fading in, rows loading) and differs
        from what was read last time. Comparing with the last read, not with the previous frame,
        means slow changes add up instead of slipping through one small step at a time.
        """
        try:
            if not self._active():
                return 0  # the game is not in front: do no work at all
            frame = self._grab()
            if frame is None:
                return 0
            self._last_frame = frame
            left, top, right, bottom = region(frame, SCAN_REGION)
            thumb = self._thumb(frame, (left, top, right, bottom))
            previous, self._last_thumb = self._last_thumb, thumb
            # Reading the list costs about a second of CPU, so first look at the tab bar's key boxes (pixels only).
            if not self._exchange_open(frame):
                return 0
            self._exchange_seen_at = time.monotonic()
            if self._differs(thumb, previous):
                return 0  # still moving: read it once it settles
            if not (self._rechecks or self._differs(thumb, self._read_thumb)):
                return 0
            self._read_thumb = thumb
            recheck = self._rechecks > 0
            self._rechecks = max(0, self._rechecks - 1)
            words = self._read(frame.crop((left, top, right, bottom)), (left, top))
            if classify(words) == Screen.SELL:
                words = words + self._read_panel_title(frame)
            observations = observations_from_words(words, self._contributor, now)
            self.skipped_all_grades = buy_tab_on_all_grades(words)
            accepted = []
            held = False
            for obs in observations:
                if obs.kind == "buy" or self._passes_guard(obs):
                    accepted.append(obs)
                else:
                    held = True
            if not held:
                self._rechecks = 0
            elif not recheck:
                self._rechecks = _MAX_RECHECKS  # read the same list again soon: a real price shows up twice
            if accepted:
                self._store.add(accepted)
            keys = {(name_key(o.key.name), o.key.category, o.key.grade) for o in accepted}
            self.last_new = len(keys - self._seen)
            self._seen |= keys
            self.session_total = len(self._seen)
            if accepted:
                self.last_rows, self.last_label = len(accepted), _describe(accepted[0])
            return len(accepted)
        except Exception:
            log.exception("scan failed")
            return 0

    def _read_panel_title(self, frame: Image.Image) -> list[Word]:
        left, top, right, bottom = region(frame, PANEL_TITLE_REGION)
        crop = frame.crop((left, top, right, bottom))
        return [w for w in read_header(self._read, crop, (left, top)) if w.x >= left]

    def _passes_guard(self, obs: Observation) -> bool:
        if accept(obs, typical_sell(self._store.recent_sells(obs.key, _GUARD_HISTORY))):
            self._held.pop(obs.key, None)
            return True
        value = (obs.avg, obs.low)
        if self._held.get(obs.key) == value:  # the same odd value twice in a row is believed
            del self._held[obs.key]
            return True
        log.info("held back %s (grade %s): avg %s, low %s looks like a misread; believed if read again",
                 obs.key.name, obs.key.grade, obs.avg, obs.low)
        self._held[obs.key] = value
        return False
