"""Parse the Exchange Sell tab (the player's backpack with AVG. and LOW prices)."""

from dune_market.models import SellRow, Word
from dune_market.ocr import find_grade_badge, name_key, name_line, name_line_extent, normalize_category, normalize_name, parse_price


def _center(word: Word) -> float:
    return word.x + word.w / 2


def _compact(text: str) -> str:
    return "".join(text.split()).upper()


def _find(words: list[Word], fragment: str) -> Word | None:
    return next((w for w in words if fragment in _compact(w.text)), None)


def _read_panel(words: list[Word], right_edge: float) -> tuple[str | None, str | None, str | None]:
    """Name, category and grade shown in the item detail panel (the selected row)."""
    panel = [w for w in words if _center(w) >= right_edge]
    for cat in sorted((w for w in panel if normalize_category(w.text)), key=lambda w: w.y):
        below = [
            w for w in panel
            if 0 < w.y - cat.y < 60 and abs(w.x - cat.x) < 60
            and normalize_category(w.text) is None and parse_price(w.text) is None
        ]
        if below:
            first = min(below, key=lambda w: w.y)
            text, line_end = name_line_extent(panel, first)
            badge = find_grade_badge(panel, cat, line_end, first.y + first.h / 2)
            return normalize_name(text), normalize_category(cat.text), badge
    return None, None, None


def parse_sell(words: list[Word]) -> list[SellRow]:
    quantity_head = _find(words, "QUANTITY")
    avg_head = _find(words, "AVG.")
    low_head = _find(words, "LOWPRICE")
    if not (quantity_head and avg_head and low_head):
        return []

    columns = {"quantity": _center(quantity_head), "avg": _center(avg_head), "low": _center(low_head)}
    spacing = columns["low"] - columns["avg"]
    right_edge = columns["low"] + spacing / 2
    name_edge = columns["quantity"] - spacing / 2
    header_bottom = max(quantity_head.y, avg_head.y, low_head.y) + max(quantity_head.h, avg_head.h)

    # Everything above the header (character name, Solari balance) and right of
    # the table (item detail panel) is ignored.
    body = [w for w in words if w.y > header_bottom and _center(w) < right_edge]
    categories = sorted(
        (w for w in body if w.x < name_edge and normalize_category(w.text)),
        key=lambda w: w.y,
    )

    panel_name, panel_category, panel_grade = _read_panel(words, right_edge)

    rows = []
    for i, cat in enumerate(categories):
        top = cat.y - 15
        bottom = categories[i + 1].y - 15 if i + 1 < len(categories) else cat.y + 130
        band = [w for w in body if top <= w.y < bottom]

        names = [
            w for w in band
            if w.y > cat.y and abs(w.x - cat.x) < 60 and w.x < name_edge
            and normalize_category(w.text) is None and parse_price(w.text) is None
        ]
        if not names:
            continue
        name = normalize_name(name_line(band, min(names, key=lambda w: w.y)))

        values: dict[str, int] = {}
        for column, center in columns.items():
            candidates = [
                w for w in band
                if abs(_center(w) - center) < spacing / 2 and parse_price(w.text) is not None
            ]
            if candidates:
                values[column] = parse_price(min(candidates, key=lambda w: abs(_center(w) - center)).text)

        if "avg" not in values or "low" not in values:
            continue
        category = normalize_category(cat.text)
        selected = panel_name is not None and name_key(name) == name_key(panel_name) and category == panel_category
        rows.append(
            SellRow(
                category=category,
                name=name,
                grade=panel_grade if selected else None,
                quantity=values.get("quantity"),
                avg_price=values["avg"],
                low_price=values["low"],
            )
        )
    return rows
