from dune_market.models import SellRow
from dune_market.parse_sell import parse_sell

# (category, name, quantity, avg, low) read off screenshots/sell.png
EXPECTED = [
    ("MISC - COMPONENTS", "Atmospheric Filtered Fabric", 24, 56359, 46000),
    ("MISC - COMPONENTS", "Calibrated Servok", 11, 105825, 77110),
    ("MISC - REFINEDRESOURCES", "Cobalt Paste", 14, 19283, 8900),
    ("MISC - COMPONENTS", "Complex Machinery", 48, 267820, 40000),
    ("MISC - REFINEDRESOURCES", "Duraluminum Ingot", 3, 19988, 17888),
    ("MISC - COMPONENTS", "EMF Generator", 3, 2508, 1899),
]


def _check_rows(rows: list[SellRow]):
    by_name = {r.name: r for r in rows}
    assert len(rows) == len(EXPECTED)
    for category, name, quantity, avg, low in EXPECTED:
        row = by_name[name]
        assert (row.category, row.avg_price, row.low_price) == (category, avg, low)
        # quantity is a dim column the OCR often misses; a wrong value is a bug, a missing one is not
        assert row.quantity in (None, quantity)


def test_parse_sell_rows_from_screenshot(shot_words):
    rows = parse_sell(shot_words("sell"))
    _check_rows(rows)
    assert {r.name: r.quantity for r in rows}["Complex Machinery"] == 48


def test_parse_sell_never_includes_character_name(shot_words):
    rows = parse_sell(shot_words("sell"))
    assert all("Passu" not in r.name and "Passu" not in r.category for r in rows)


def test_parse_sell_scaled_screenshot(shot_words):
    _check_rows(parse_sell(shot_words("sell", scale=0.75)))


def test_parse_sell_empty():
    assert parse_sell([]) == []
