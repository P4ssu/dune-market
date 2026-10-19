"""Find the inventory tooltip header (category line + item name) near the cursor."""

import math

from dune_market.models import Word
from dune_market.ocr import normalize_category, normalize_name, parse_price


def parse_tooltip(words: list[Word], cursor: tuple[int, int]) -> tuple[str, str] | None:
    """Return (name, category) of the tooltip header closest to the cursor."""
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
        distance = math.hypot(cat.x + cat.w / 2 - cursor[0], cat.y + cat.h / 2 - cursor[1])
        if best is None or distance < best[0]:
            best = (distance, normalize_name(name.text), category)
    return None if best is None else (best[1], best[2])
