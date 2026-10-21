"""What the price popup says and where it goes (pure logic, no GUI)."""

import html as _html
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from PIL import Image

from dune_market.models import ItemStats, Word
from dune_market.ocr import read_header, read_words
from dune_market.banner import find_banner
from dune_market.parse_tooltip import find_tooltip
from dune_market.screens import exchange_tab_open
from dune_market.stats import STALE_AFTER
from dune_market.store import PriceStore

log = logging.getLogger(__name__)

GOLD, TEXT, MUTED = "#e6c984", "#f1e8d2", "#a09580"
GREEN, RED, AMBER = "#86d493", "#ea7d70", "#e8aa4a"
_TREND_RE = re.compile(r"^(.*?)\s([▲▼])\s(\S+)$")

_LINE_HEIGHT = 28  # approximate popup line height in pixels, used to place it above the tooltip


@dataclass(frozen=True)
class PopupData:
    lines: list[str]
    x: int
    y: int
    anchor: tuple[int, int, int, int] | None = None  # the tooltip banner (x, y, w, h) the popup is built for


def _age(updated_at: datetime, now: datetime) -> str:
    seconds = max(0, int((now - updated_at).total_seconds()))
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    return f"{seconds // 86400} d ago"


def _block(s: ItemStats, now: datetime) -> list[str]:
    lines = ["Grade unknown" if s.key.grade == "unknown" else f"Grade: {s.key.grade}"]
    lowest = "n/a" if s.lowest is None else f"{s.lowest:,}"
    if s.lowest is not None and s.trend_pct:
        lowest += f" {'▲' if s.trend_pct > 0 else '▼'} {abs(s.trend_pct):g}%"
    lines.append(f"Lowest: {lowest}")
    average = "n/a" if s.avg is None else f"{s.avg:,}"
    if s.avg is not None and s.avg_at and s.updated_at - s.avg_at > STALE_AFTER:
        average += f" ({_age(s.avg_at, now)})"  # older than the other numbers
    if s.avg_from_listings:
        average += " (listings)"
    lines.append(f"Average: {average}")
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
    exchange_open: Callable[[Image.Image], bool] | None = None,
    header_cache: dict | None = None,
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
    if exchange_open(frame) if exchange_open else exchange_tab_open(frame):
        return None

    margin = 6
    crop, origin = _crop(frame, banner.x - margin, banner.y - margin,
                         banner.x + banner.w + margin, banner.y + banner.h + margin)
    # The same item draws the same pixels, so what was read from them once is remembered.
    key = hash(crop.tobytes())
    hit = header_cache.get(key) if header_cache is not None else None
    if hit is None:
        hit = find_tooltip(read_header(read, crop, origin), cursor)
        if hit is None:
            return None
        if header_cache is not None:
            if len(header_cache) >= 512:
                header_cache.clear()
            header_cache[key] = hit

    stats = select_stats(store.lookup(hit.name, hit.category, now), hit.grade)
    lines = format_popup(hit.name, stats, now)
    y = max(0, banner.y - _LINE_HEIGHT * len(lines) - 24)
    return PopupData(lines, banner.x, y, anchor=(banner.x, banner.y, banner.w, banner.h))


class HoverTracker:
    """Decides when to look up and when to show or hide the popup.

    After the cursor rests for a moment it keeps looking for a tooltip for a couple of seconds (the
    game shows tooltips a little late). Once a popup is up it stays while the same tooltip is under
    the cursor (`still_visible`), so small mouse movements on the item do not hide it.
    """

    def __init__(
        self,
        lookup: Callable[[tuple[int, int]], PopupData | None],
        on_show: Callable[[PopupData], None],
        on_hide: Callable[[], None],
        still_seconds: float = 0.1,
        jitter_px: int = 8,
        current_cursor: Callable[[], tuple[int, int]] | None = None,
        still_visible: Callable[[PopupData, tuple[int, int]], bool] | None = None,
        retry_seconds: float = 0.15,
        give_up_seconds: float = 2.0,
    ):
        self._lookup = lookup
        self._on_show = on_show
        self._on_hide = on_hide
        self._still_seconds = still_seconds
        self._jitter_px = jitter_px
        self._current_cursor = current_cursor
        self._still_visible = still_visible
        self._retry_seconds = retry_seconds
        self._give_up_seconds = give_up_seconds
        self._anchor: tuple[int, int] | None = None
        self._next_try: float | None = None
        self._give_up_at = 0.0
        self._popup: PopupData | None = None

    def _moved(self, cursor: tuple[int, int]) -> bool:
        a = self._anchor
        return a is None or max(abs(cursor[0] - a[0]), abs(cursor[1] - a[1])) > self._jitter_px

    def tick(self, cursor: tuple[int, int], t: float) -> None:
        moved = self._moved(cursor)
        if self._popup is not None:
            if not moved:
                return
            self._anchor = cursor
            if self._still_visible and self._safe_still_visible(cursor):
                return  # the same tooltip is still there: keep the popup
            self._popup = None
            self._on_hide()
            self._start_waiting(t)
            return
        if moved:
            self._anchor = cursor
            self._start_waiting(t)
        elif self._next_try is not None and self._next_try <= t <= self._give_up_at:
            self._try_lookup(cursor, t)

    def _start_waiting(self, t: float) -> None:
        self._next_try = t + self._still_seconds
        self._give_up_at = t + self._still_seconds + self._give_up_seconds

    def _safe_still_visible(self, cursor: tuple[int, int]) -> bool:
        try:
            return bool(self._still_visible(self._popup, cursor))
        except Exception:
            log.exception("tooltip check failed")
            return False

    def _try_lookup(self, cursor: tuple[int, int], t: float) -> None:
        self._next_try = t + self._retry_seconds
        try:
            popup = self._lookup(cursor)
        except Exception:
            log.exception("hover lookup failed")
            return
        if popup and not self._moved_away(cursor):
            self._popup = popup
            self._next_try = None
            self._on_show(popup)

    def _moved_away(self, cursor: tuple[int, int]) -> bool:
        """True if the cursor left while the lookup ran (a slow lookup must not flash a stale popup)."""
        if self._current_cursor is None:
            return False
        now = self._current_cursor()
        return max(abs(now[0] - cursor[0]), abs(now[1] - cursor[1])) > self._jitter_px


def _esc(text: str) -> str:
    return _html.escape(text, quote=False)


def render_html(lines: list[str]) -> str:
    """Rich text for the popup: title, one section per grade, label/value rows, a muted footer."""
    title, *rest = lines
    rows = []
    for line in rest:
        if line.startswith("Grade"):
            grade = line.removeprefix("Grade").removeprefix(":").strip().upper()
            spacer = '<tr><td colspan="2" style="font-size:3pt">&nbsp;</td></tr>' if rows else ""
            rows.append(f'{spacer}<tr><td colspan="2" style="color:{GOLD};font-size:8pt">GRADE {_esc(grade)}</td></tr>')
        elif line.startswith("Updated"):
            color = AMBER if line.endswith("(old)") else MUTED
            rows.append(f'<tr><td colspan="2" style="color:{color};font-size:8pt">{_esc(line)}</td></tr>')
        elif ": " in line:
            label, value = line.split(": ", 1)
            trend = ""
            match = _TREND_RE.match(value)
            if match:
                value, arrow, pct = match.groups()
                trend = f' <span style="color:{GREEN if arrow == "▲" else RED}">{arrow} {_esc(pct)}</span>'
            emphasis = GOLD if label == "Lowest" else TEXT
            rows.append(
                f'<tr><td style="color:{MUTED}">{_esc(label)}</td>'
                f'<td align="right" style="color:{emphasis};font-weight:600">{_esc(value)}{trend}</td></tr>'
            )
        else:
            rows.append(f'<tr><td colspan="2" style="color:{MUTED}">{_esc(line)}</td></tr>')
    return (
        f'<div style="color:{GOLD};font-size:13pt;font-weight:600">{_esc(title)}</div>'
        f'<table width="100%" cellspacing="0" cellpadding="3" style="margin-top:4px">{"".join(rows)}</table>'
    )


def scan_toast_lines(label: str, rows: int, new: int, total: int) -> list[str]:
    """The in-game notice shown while the scanner is reading the Exchange."""
    return [
        "Dune Market · scanning",
        label,
        f"{rows} rows read · {new} new items · {total} items this session",
    ]


def render_toast_html(lines: list[str]) -> str:
    head, *rest = lines
    body = "".join(
        f'<div style="color:{TEXT if i == 0 else MUTED};font-size:{"10pt" if i == 0 else "9pt"}">{_esc(line)}</div>'
        for i, line in enumerate(rest)
    )
    return f'<div style="color:{GOLD};font-size:8pt">{_esc(head.upper())}</div>{body}'
