"""What the price popup says and where it goes (pure logic, no GUI)."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from PIL import Image

from dune_market.models import ItemStats, Word
from dune_market.ocr import read_header, read_words
from dune_market.banner import find_banner
from dune_market.parse_tooltip import find_tooltip
from dune_market.screens import exchange_tab_open
from dune_market.store import PriceStore

log = logging.getLogger(__name__)

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


def select_stats(stats: list[ItemStats], grade: str) -> list[ItemStats]:
    """The stats that fit the hovered item's grade: exact grade, else grade-unknown, else whatever exists."""
    exact = [s for s in stats if s.key.grade == grade]
    if exact:
        return exact
    unknown = [s for s in stats if s.key.grade == "unknown"]
    return unknown or stats


def _crop(frame: Image.Image, left: float, top: float, right: float, bottom: float) -> tuple[Image.Image, tuple[int, int]]:
    width, height = frame.size
    box = (max(0, int(left)), max(0, int(top)), min(width, int(right)), min(height, int(bottom)))
    return frame.crop(box), (box[0], box[1])


def hover_popup(
    frame: Image.Image | None,
    cursor: tuple[int, int],
    store: PriceStore,
    now: datetime,
    read: Callable[..., list[Word]] = read_words,
) -> PopupData | None:
    """The popup for the inventory tooltip under the cursor, or None.

    The tooltip header banner is found by its gold border lines (no OCR), so hovering where there
    is no tooltip costs almost nothing, and only a tiny crop of the banner is OCR'd.
    """
    if frame is None:
        return None
    width, height = frame.size
    if not (0 <= cursor[0] < width and 0 <= cursor[1] < height):
        return None  # cursor on another monitor
    banner = find_banner(frame, cursor)
    if banner is None:
        return None

    # Exchange tabs have banners and category lines too (the detail panel), so stay quiet
    # whenever an Exchange tab is open.
    if exchange_tab_open(frame, read):
        return None

    margin = 6
    crop, origin = _crop(frame, banner.x - margin, banner.y - margin,
                         banner.x + banner.w + margin, banner.y + banner.h + margin)
    hit = find_tooltip(read_header(read, crop, origin), cursor)
    if hit is None:
        return None

    stats = select_stats(store.lookup(hit.name, hit.category, now), hit.grade)
    lines = format_popup(hit.name, stats, now)
    y = max(0, banner.y - _LINE_HEIGHT * len(lines) - 24)
    return PopupData(lines, banner.x, y)


class HoverTracker:
    """Fires `lookup` once when the cursor has rested, and hides the popup when it moves."""

    def __init__(
        self,
        lookup: Callable[[tuple[int, int]], PopupData | None],
        on_show: Callable[[PopupData], None],
        on_hide: Callable[[], None],
        still_seconds: float = 0.4,
        jitter_px: int = 8,
        current_cursor: Callable[[], tuple[int, int]] | None = None,
    ):
        self._lookup = lookup
        self._on_show = on_show
        self._on_hide = on_hide
        self._still_seconds = still_seconds
        self._jitter_px = jitter_px
        self._current_cursor = current_cursor
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
            if popup and not self._moved_away(cursor):
                self._visible = True
                self._on_show(popup)

    def _moved_away(self, cursor: tuple[int, int]) -> bool:
        """True if the cursor left while the lookup ran (a slow lookup must not flash a stale popup)."""
        if self._current_cursor is None:
            return False
        now = self._current_cursor()
        return max(abs(now[0] - cursor[0]), abs(now[1] - cursor[1])) > self._jitter_px
