from dune_market.models import Word
from dune_market.ocr import name_line, normalize_category, normalize_name, parse_price


def test_parse_price_handles_commas():
    assert parse_price("56,359") == 56359


def test_parse_price_strips_solari_symbol():
    assert parse_price("56,359 S") == 56359


def test_parse_price_rejects_text():
    assert parse_price("abc") is None


def test_read_words_finds_atmospheric_fabric(shot_words):
    words = shot_words("sell")
    assert any("Fabric" in w.text for w in words)


def test_parse_price_handles_attached_symbol():
    assert parse_price("56,359@") == 56359
    assert parse_price("46,000S") == 46000


def test_parse_price_drops_icon_misread_as_digit():
    assert parse_price("46,0005") == 46000


def test_normalize_category_restores_hyphen_spacing():
    assert normalize_category("MISC-COMPONENTS") == "MISC - COMPONENTS"
    assert normalize_category("MISC - REFINED RESOURCES") == "MISC - REFINEDRESOURCES"


def test_normalize_category_rejects_non_category():
    assert normalize_category("Atmospheric Filtered Fabric") is None
    assert normalize_category("BACKPACK") is None


def test_normalize_name_splits_joined_words():
    assert normalize_name("AtmosphericFiltered Fabric") == "Atmospheric Filtered Fabric"
    assert normalize_name("EMFGenerator") == "EMF Generator"
    assert normalize_name("CollapsibleDewReaperMk6") == "Collapsible Dew Reaper Mk6"
    assert normalize_name("Spice-infused Plastanium Dust") == "Spice-infused Plastanium Dust"


def test_name_line_joins_spans_the_ocr_split():
    first = Word("Spice-infused Plastanium", 994, 883, 320, 30)
    words = [
        first,
        Word("Dust", 1317, 889, 56, 19),  # same line, small gap: part of the name
        Word("Far Away", 1900, 886, 80, 20),  # same line, big gap: not part of the name
        Word("Next line", 996, 940, 100, 20),  # different line
    ]
    assert name_line(words, first) == "Spice-infused Plastanium Dust"


def test_name_line_single_span():
    first = Word("Cobalt Paste", 286, 757, 164, 32)
    assert name_line([first], first) == "Cobalt Paste"
