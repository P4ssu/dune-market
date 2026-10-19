from dune_market.ocr import parse_price


def test_parse_price_handles_commas():
    assert parse_price("56,359") == 56359


def test_parse_price_strips_solari_symbol():
    assert parse_price("56,359 S") == 56359


def test_parse_price_rejects_text():
    assert parse_price("abc") is None


def test_read_words_finds_atmospheric_fabric(shot_words):
    words = shot_words("sell")
    assert any("Fabric" in w.text for w in words)
