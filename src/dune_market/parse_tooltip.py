"""Find the inventory tooltip header (category line + item name) near the cursor."""

import math
from dataclasses import dataclass

from dune_market.models import Word
from dune_market.ocr import find_grade_badge, name_line_extent, normalize_category, normalize_name, parse_price


@dataclass(frozen=True)
class TooltipHit:
    name: str
    category: str
    x: float  # top-left of the category line, in frame pixels
    y: float
    w: float
    h: float
    grade: str = "0"  # the number at the right end of the header; no number means grade 0


def find_tooltip(words: list[Word], cursor: tuple[int, int]) -> TooltipHit | None:
    """The tooltip header closest to the cursor, with its position."""
    best = None
    for cat in words:
        category = normalize_category(cat.text)
        if category is None:
            continue
        below = [
            w for w in words
            if 0 < w.y - cat.y < 60 and abs(w.x - cat.x) < 60
            and normalize_category(w.text) is None and parse_price(w.text) is None
        ]
        if not below:
            continue
        name = min(below, key=lambda w: w.y)
        text, line_end = name_line_extent(words, name)
        grade = find_grade_badge(words, cat, line_end, name.y + name.h / 2)
        distance = math.hypot(cat.x + cat.w / 2 - cursor[0], cat.y + cat.h / 2 - cursor[1])
        if best is None or distance < best[0]:
            best = (distance, TooltipHit(normalize_name(text), category, cat.x, cat.y, cat.w, cat.h, grade))
    return None if best is None else best[1]


def parse_tooltip(words: list[Word], cursor: tuple[int, int]) -> tuple[str, str] | None:
    """Return (name, category) of the tooltip header closest to the cursor."""
    hit = find_tooltip(words, cursor)
    return None if hit is None else (hit.name, hit.category)
