"""What the price popup says and where it goes (pure logic, no GUI)."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from PIL import Image

from dune_market.models import ItemStats, Word
from dune_market.ocr import read_words
from dune_market.parse_tooltip import find_tooltip
from dune_market.store import PriceStore

log = logging.getLogger(__name__)

_HEADER_BAND = 0.12  # top fraction of the frame holding the Exchange tab names
_HEADER_X = (0.35, 0.65)  # ...and the centre part of it; the corners hold the character name and Solari balance
_REGION_W, _REGION_H = 0.20, 0.25  # half-size of the crop around the cursor, as frame fractions
_HEADER_READ_W = 0.30  # width of the second, header-only crop, as a frame fraction
_LINE_HEIGHT = 28  # approximate popup line height in pixels, used to place it above the tooltip


@dataclass(frozen=True)
class PopupData:
    lines: list[str]
    x: int
    y: int


def _age(updated_at: datetime, now: datetime) -> str:
    seconds = max(0, int((now - updated_at).total_seconds()))
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    return f"{seconds // 86400} d ago"


def _block(s: ItemStats, now: datetime) -> list[str]:
    lines = ["Grade unknown" if s.key.grade == "unknown" else f"Grade: {s.key.grade}"]
    avg = "n/a" if s.avg is None else f"{s.avg:,}"
    if s.avg is not None and s.trend_pct:
        avg += f" {'▲' if s.trend_pct > 0 else '▼'} {abs(s.trend_pct):g}%"
    lines.append(f"Avg price: {avg}")
    lines.append(f"Cheapest now: {'n/a' if s.cheapest is None else f'{s.cheapest:,}'}")
    if s.listing_count is not None:
        lines.append(f"Listings: {s.listing_count}")
    lines.append(f"Updated {_age(s.updated_at, now)} by {s.contributor}" + (" (old)" if s.stale else ""))
    return lines


def format_popup(name: str, stats: list[ItemStats], now: datetime) -> list[str]:
    """Popup lines (layout "B"): one block per known grade, newest first."""
    if not stats:
        return [name, "No price data yet"]
    lines = [name]
    for s in stats:
        lines += _block(s, now)
    return lines


def hover_popup(
    frame: Image.Image | None,
    cursor: tuple[int, int],
    store: PriceStore,
    now: datetime,
    read: Callable[[Image.Image, tuple[int, int]], list[Word]] = read_words,
) -> PopupData | None:
    """The popup for the inventory tooltip under the cursor, or None."""
    if frame is None:
        return None
    width, height = frame.size

    # Exchange tabs list items with the same category-line pattern as tooltips,
    # so stay quiet whenever an Exchange tab is open.
    header_left = int(width * _HEADER_X[0])
    header = read(frame.crop((header_left, 0, int(width * _HEADER_X[1]), int(height * _HEADER_BAND))), (header_left, 0))
    if any("MYORDERS" in "".join(w.text.split()).upper() for w in header):
        return None

    left = max(0, int(cursor[0] - width * _REGION_W))
    top = max(0, int(cursor[1] - height * _REGION_H))
    right = min(width, int(cursor[0] + width * _REGION_W))
    bottom = min(height, int(cursor[1] + height * _REGION_H))
    hit = find_tooltip(read(frame.crop((left, top, right, bottom)), (left, top)), cursor)
    if hit is None:
        return None

    # The first crop can cut the header text short, so read the header again
    # with a crop that extends well past it.
    left = max(0, int(hit.x) - 30)
    top = max(0, int(hit.y) - 10)
    right = min(width, int(hit.x + width * _HEADER_READ_W))
    bottom = min(height, int(hit.y) + 90)
    hit = find_tooltip(read(frame.crop((left, top, right, bottom)), (left, top)), (int(hit.x), int(hit.y))) or hit

    lines = format_popup(hit.name, store.lookup(hit.name, hit.category, now), now)
    y = max(0, int(hit.y) - _LINE_HEIGHT * len(lines) - 24)
    return PopupData(lines, int(hit.x), y)


class HoverTracker:
    """Fires `lookup` once when the cursor has rested, and hides the popup when it moves."""

    def __init__(
        self,
        lookup: Callable[[tuple[int, int]], PopupData | None],
        on_show: Callable[[PopupData], None],
        on_hide: Callable[[], None],
        still_seconds: float = 0.4,
        jitter_px: int = 8,
    ):
        self._lookup = lookup
        self._on_show = on_show
        self._on_hide = on_hide
        self._still_seconds = still_seconds
        self._jitter_px = jitter_px
        self._anchor: tuple[int, int] | None = None
        self._still_since = 0.0
        self._handled = False
        self._visible = False

    def tick(self, cursor: tuple[int, int], t: float) -> None:
        moved = self._anchor is None or max(abs(cursor[0] - self._anchor[0]), abs(cursor[1] - self._anchor[1])) > self._jitter_px
        if moved:
            self._anchor, self._still_since, self._handled = cursor, t, False
            if self._visible:
                self._visible = False
                self._on_hide()
        elif not self._handled and t - self._still_since >= self._still_seconds:
            self._handled = True
            try:
                popup = self._lookup(cursor)
            except Exception:
                log.exception("hover lookup failed")
                return
            if popup:
                self._visible = True
                self._on_show(popup)
