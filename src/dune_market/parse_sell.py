"""Parse the Exchange Sell tab (the player's backpack with AVG. and LOW prices)."""

from dune_market.models import SellRow, Word
from dune_market.ocr import normalize_category, normalize_name, parse_price


def _center(word: Word) -> float:
    return word.x + word.w / 2


def _compact(text: str) -> str:
    return "".join(text.split()).upper()


def _find(words: list[Word], fragment: str) -> Word | None:
    return next((w for w in words if fragment in _compact(w.text)), None)


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
        name = normalize_name(min(names, key=lambda w: w.y).text)

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
        rows.append(
            SellRow(
                category=normalize_category(cat.text),
                name=name,
                quantity=values.get("quantity"),
                avg_price=values["avg"],
                low_price=values["low"],
            )
        )
    return rows
