"""Parse the Exchange Buy tab (one row per market listing)."""

import re

from dune_market.models import BuyRow, Word
from dune_market.ocr import name_line, normalize_category, normalize_name, parse_price

_EXPIRATION_RE = re.compile(r"^(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$")
_GRADE_RE = re.compile(r"GRADE:?(.+)", re.IGNORECASE)


def _center(word: Word) -> float:
    return word.x + word.w / 2


def _compact(text: str) -> str:
    return "".join(text.split())


def _find(words: list[Word], fragment: str) -> Word | None:
    return next((w for w in words if fragment in _compact(w.text).upper()), None)


def parse_expiration(text: str) -> int | None:
    """Seconds left from text like "2h 21m 13s" or "2d 6h 42m"."""
    match = _EXPIRATION_RE.match(_compact(text).lower())
    if not match or not any(match.groups()):
        return None
    days, hours, minutes, seconds = (int(g or 0) for g in match.groups())
    return ((days * 24 + hours) * 60 + minutes) * 60 + seconds


def _read_grade(words: list[Word]) -> str:
    for word in words:
        match = _GRADE_RE.search(_compact(word.text))
        if match:
            return match.group(1).lower()
    return "all"


def parse_buy(words: list[Word]) -> tuple[str, list[BuyRow]]:
    """Return (grade filter label, listing rows). Grade is "all" when unreadable."""
    grade = _read_grade(words)
    price_head = _find(words, "PRICE")
    expiry_head = _find(words, "EXPIRATION")
    name_head = _find(words, "NAME")
    if not (price_head and expiry_head and name_head):
        return grade, []

    price_center = _center(price_head)
    expiry_center = _center(expiry_head)
    spacing = expiry_center - price_center
    right_edge = expiry_center + spacing / 2
    price_edge = price_center - spacing / 2
    header_bottom = max(price_head.y, expiry_head.y) + price_head.h

    body = [w for w in words if w.y > header_bottom and _center(w) < right_edge]
    categories = sorted(
        (w for w in body if w.x >= name_head.x and w.x < price_edge and normalize_category(w.text)),
        key=lambda w: w.y,
    )

    rows = []
    for i, cat in enumerate(categories):
        top = cat.y - 15
        bottom = categories[i + 1].y - 15 if i + 1 < len(categories) else cat.y + 130
        band = [w for w in body if top <= w.y < bottom]

        names = [
            w for w in band
            if w.y > cat.y and abs(w.x - cat.x) < 60 and normalize_category(w.text) is None
        ]
        prices = [w for w in band if abs(_center(w) - price_center) < spacing / 2 and parse_price(w.text)]
        expiries = [
            w for w in band
            if abs(_center(w) - expiry_center) < spacing / 2 and parse_expiration(w.text) is not None
        ]
        if not (names and prices and expiries):
            continue  # a row cut off by the bottom of the list
        rows.append(
            BuyRow(
                category=normalize_category(cat.text),
                name=normalize_name(name_line(band, min(names, key=lambda w: w.y))),
                price=parse_price(prices[0].text),
                expires_in_s=parse_expiration(expiries[0].text),
            )
        )
    return grade, rows
