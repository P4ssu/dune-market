from dune_market.models import Word
from dune_market.parse_tooltip import find_tooltip, parse_tooltip


def test_tooltip_item(shot_words):
    result = parse_tooltip(shot_words("item hover"), (842, 927))
    assert result == ("Spice-infused Plastanium Dust", "MISC - COMPONENTS")


def test_tooltip_schematic_trigger(shot_words):
    result = parse_tooltip(shot_words("schematic hover"), (531, 620))
    assert result == ("Quick-release Trigger", "SCHEMATIC - UNIQUE")


def test_tooltip_blueprint_gauntlets(shot_words):
    result = parse_tooltip(shot_words("blueprint hover"), (223, 620))
    assert result == ("Mendek's Gauntlets", "SCHEMATIC - UNIQUE")


def test_tooltip_none_without_tooltip():
    assert parse_tooltip([], (0, 0)) is None


def test_tooltip_ignores_ui_labels():
    words = [Word(t, 100, 100 + 40 * i, 100, 30) for i, t in enumerate(["CHARACTER", "LOADOUT", "Show Stats"])]
    assert parse_tooltip(words, (100, 100)) is None


def test_tooltip_picks_header_closest_to_cursor():
    words = [
        Word("MISC-COMPONENTS", 100, 100, 240, 26), Word("Far Item", 100, 128, 150, 28),
        Word("SCHEMATIC-UNIQUE", 1500, 800, 240, 26), Word("Near Item", 1500, 828, 150, 28),
    ]
    assert parse_tooltip(words, (1450, 850)) == ("Near Item", "SCHEMATIC - UNIQUE")


def test_find_tooltip_returns_header_box(shot_words):
    hit = find_tooltip(shot_words("schematic hover"), (531, 620))
    assert (hit.name, hit.category) == ("Quick-release Trigger", "SCHEMATIC - UNIQUE")
    assert 600 < hit.x < 700 and 330 < hit.y < 370 and hit.w > 200
