"""Find the inventory tooltip's header banner by its gold border lines (no OCR, a few milliseconds).

The banner is a dark band framed by two long thin gold lines, about 0.23 of the screen width long
and 0.028 of the screen width apart. Locating it first means only a tiny crop has to be OCR'd.
"""

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image

_MIN_LINE = 0.18  # a border line is at least this fraction of the frame width long
_LINE_GAP = (0.022, 0.034)  # distance between the two lines, as a fraction of the frame width (UI scale follows the width)
_SEARCH_UP, _SEARCH_DOWN = 0.60, 0.30  # how far above/below the cursor to look, as frame fractions (full width, so lines are never cut);
# tall tooltips (armor: description plus stats) put their header far above the hovered slot


@dataclass(frozen=True)
class Banner:
    x: int
    y: int
    w: int
    h: int


def gold_mask(pixels: np.ndarray) -> np.ndarray:
    r, g, b = (pixels[..., i].astype(np.int16) for i in range(3))
    return (r > 110) & (r - b > 40) & (r >= g) & (g - b > 15)


def _runs(mask: np.ndarray, min_length: int) -> list[tuple[int, int, int]]:
    """(row, start, length) of every horizontal run of True at least `min_length` long."""
    runs = []
    for y in np.nonzero(mask.sum(axis=1) >= min_length)[0]:
        edges = np.diff(np.concatenate(([0], mask[y].astype(np.int8), [0])))
        for start, end in zip(np.nonzero(edges == 1)[0], np.nonzero(edges == -1)[0]):
            if end - start >= min_length:
                runs.append((int(y), int(start), int(end - start)))
    return runs


def find_banner(frame: Image.Image, cursor: tuple[int, int]) -> Banner | None:
    """The banner (pair of gold lines) closest to the cursor, or None."""
    width, height = frame.size
    left, top = 0, max(0, int(cursor[1] - height * _SEARCH_UP))
    right, bottom = width, min(height, int(cursor[1] + height * _SEARCH_DOWN))
    if bottom <= top:
        return None
    runs = _runs(gold_mask(np.asarray(frame.crop((left, top, right, bottom)))), int(width * _MIN_LINE))

    best = None
    for y1, x1, n1 in runs:
        for y2, x2, n2 in runs:
            gap = y2 - y1
            if not (width * _LINE_GAP[0] <= gap <= width * _LINE_GAP[1]):
                continue
            if abs(x1 - x2) > 8 or abs(n1 - n2) > 12:
                continue
            banner = Banner(left + x1, top + y1, n1, gap)
            distance = math.hypot(banner.x + banner.w / 2 - cursor[0], banner.y + banner.h / 2 - cursor[1])
            if best is None or distance < best[0]:
                best = (distance, banner)
    return None if best is None else best[1]
