from dune_market.parse_buy import parse_buy, parse_expiration

CATEGORY = "GARMENTS - LIGHTARMOR"
EXPECTED = {
    "The Forge Boots": 8473,
    "The Forge Chestpiece": 8480,
    "The Forge Gloves": 8485,
    "The Forge Helmet": 8491,
    "The Forge Pants": 8496,
}  # name -> seconds left, read off screenshots/buy tab.png (all priced 10,000,000)


def test_parse_expiration_formats():
    assert parse_expiration("2h21m13s") == 8473
    assert parse_expiration("2d 6h 42m") == 196920
    assert parse_expiration("9h 23m 1s") == 33781
    assert parse_expiration("abc") is None


def _check_rows(rows):
    assert {r.name: r.expires_in_s for r in rows} == EXPECTED
    assert all(r.price == 10_000_000 and r.category == CATEGORY for r in rows)


def test_parse_buy_rows_from_screenshot(shot_words):
    grade, rows = parse_buy(shot_words("buy tab"))
    _check_rows(rows)
    assert rows[0].name == "The Forge Boots"


def test_parse_buy_grade_all(shot_words):
    grade, _ = parse_buy(shot_words("buy tab"))
    assert grade == "all"


def test_parse_buy_scaled_screenshot(shot_words):
    _, rows = parse_buy(shot_words("buy tab", scale=0.75))
    _check_rows(rows)


def test_parse_buy_ignores_partial_last_row(shot_words):
    _, rows = parse_buy(shot_words("buy tab"))
    assert len(rows) == 5


def test_parse_buy_empty():
    assert parse_buy([]) == ("all", [])
