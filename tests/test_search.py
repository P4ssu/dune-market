"""The search window: hotkey parsing, store search, rendering and the Qt window itself."""

import os
from datetime import datetime, timedelta, timezone

import pytest

from dune_market.config import load_config
from dune_market.hotkey import HotkeyListener, parse_hotkey
from dune_market.models import ItemKey, Observation
from dune_market.search import SEARCH_HINT, render_search_html
from dune_market.store_sqlite import SqliteStore

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def sell(name, category, avg, low, grade="unknown", hours_ago=1, who="Mari"):
    return Observation(ItemKey(name, category, grade), "sell", NOW - timedelta(hours=hours_ago), who, avg=avg, low=low)


@pytest.fixture
def store(tmp_path):
    s = SqliteStore(str(tmp_path / "p.db"))
    s.add([
        sell("Cobalt Paste", "MISC - REFINEDRESOURCES", 19_283, 8_900),
        sell("Cobalt Paste", "MISC - REFINEDRESOURCES", 25_000, 20_000, grade="3", hours_ago=2),
        sell("Calibrated Servok", "MISC - COMPONENTS", 105_825, 77_110),
        sell("Spice Sand", "MISC - RESOURCES", 8_148, 4_500),
        sell("Robeofthe Sisterhood", "GARMENTS - LIGHTARMOR", 500, 400, grade="3"),
        sell("Mendek's Gauntlets", "SCHEMATIC - UNIQUE", 30_000, 30_000, grade="1"),
    ])
    return s


# --- hotkey text -> Windows modifiers and key code --------------------------------------------


def test_parse_hotkey_default():
    assert parse_hotkey("ctrl+shift+f") == (0x2 | 0x4, 0x46)


def test_parse_hotkey_function_key_digits_and_case():
    assert parse_hotkey("F8") == (0, 0x77)
    assert parse_hotkey("Alt+1") == (0x1, 0x31)
    assert parse_hotkey(" CTRL + SHIFT + F ") == (0x2 | 0x4, 0x46)


@pytest.mark.parametrize("text", ["", "ctrl+shift", "ctrl+shift+nope", "f8+f9", "wat+f"])
def test_parse_hotkey_rejects_nonsense(text):
    with pytest.raises(ValueError, match="hotkey"):
        parse_hotkey(text)


def test_config_reads_the_search_hotkey_and_rejects_a_bad_one(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('contributor = "Mari"\n', encoding="utf-8")
    assert load_config(str(path)).search_hotkey == "ctrl+shift+f"
    path.write_text('contributor = "Mari"\nsearch_hotkey = "F8"\n', encoding="utf-8")
    assert load_config(str(path)).search_hotkey == "F8"
    path.write_text('contributor = "Mari"\nsearch_hotkey = "ctrl+banana"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="hotkey"):
        load_config(str(path))


def test_hotkey_listener_registers_and_stops_cleanly():
    listener = HotkeyListener("ctrl+alt+shift+f24", lambda: None)  # a key nobody uses
    listener.start()
    try:
        assert listener.wait_ready(2.0)
        if not listener.registered:
            pytest.skip("no desktop session to register a hotkey in (for example a CI runner)")
        assert listener.registered is True
    finally:
        listener.stop()


# --- store search -----------------------------------------------------------------------------


def names(results):
    return [s.key.name for s in results]


def test_search_finds_by_part_of_the_name_ignoring_case_and_spacing(store):
    assert set(names(store.search("cobalt", NOW))) == {"Cobalt Paste"}
    assert set(names(store.search("COBALT PASTE", NOW))) == {"Cobalt Paste"}
    assert set(names(store.search("cobaltpaste", NOW))) == {"Cobalt Paste"}


def test_search_needs_every_word(store):
    assert store.search("cobalt servok", NOW) == []
    assert names(store.search("servok cal", NOW)) == ["Calibrated Servok"]


def test_search_matches_names_the_ocr_spelled_without_spaces(store):
    assert names(store.search("robe of the", NOW)) == ["Robeofthe Sisterhood"]


def test_search_returns_one_entry_per_grade(store):
    results = store.search("cobalt paste", NOW)
    assert sorted(s.key.grade for s in results) == ["3", "unknown"]


def test_search_ranks_names_that_start_with_the_query_first(store):
    store.add([sell("Industrial Spice Sand Filter", "MISC - COMPONENTS", 1, 1, hours_ago=0)])
    assert names(store.search("spice", NOW))[0] == "Spice Sand"


def test_search_limits_the_number_of_rows(store):
    assert len(store.search("a", NOW, limit=3)) == 3


def test_search_with_empty_or_unknown_text(store):
    assert store.search("", NOW) == []
    assert store.search("   ", NOW) == []
    assert store.search("zzzz", NOW) == []


# --- rendering --------------------------------------------------------------------------------


def test_render_lists_name_grade_prices_and_age(store):
    html = render_search_html("cobalt", store.search("cobalt", NOW), NOW)
    assert "Cobalt Paste" in html and "19,283" in html and "8,900" in html and "20,000" in html
    assert "LOWEST" in html and "AVG" in html
    assert ">3</td>" in html and ">unknown</td>" in html  # one row per grade
    assert "1 h ago" in html and "Mari" in html


def test_render_hint_for_empty_query_and_message_for_no_match():
    assert SEARCH_HINT in render_search_html("", [], NOW)
    assert "No items found" in render_search_html("zzzz", [], NOW)


def test_render_escapes_text(store):
    store.add([sell("<b>Evil</b> & Co", "X - Y", 1, 1)])
    html = render_search_html("evil", store.search("evil", NOW), NOW)
    assert "<b>Evil" not in html and "&lt;b&gt;Evil" in html


def test_render_marks_old_data():
    old = sell("Old Thing", "X - Y", 5, 4, hours_ago=30)
    from dune_market.stats import compute_stats

    html = render_search_html("old", [compute_stats(old.key, [old], NOW)], NOW)
    assert "old" in html.lower() and "1 d ago" in html


# --- the window -------------------------------------------------------------------------------


def test_search_window_filters_as_you_type_and_closes_on_escape(store):
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication

    from dune_market.overlay import SearchWindow

    app = QApplication.instance() or QApplication([])
    window = SearchWindow(store, now=lambda: NOW, restore_focus=False)
    window.open_search()
    assert window.isVisible() and SEARCH_HINT in window.results_text()
    window.input.setText("cobalt")
    assert "Cobalt Paste" in window.results_text() and "Calibrated" not in window.results_text()
    QTest.keyClick(window.input, Qt.Key.Key_Escape)
    assert not window.isVisible()
    window.open_search()
    assert window.input.text() == ""  # a fresh search each time
    window.toggle_search()
    assert not window.isVisible()
    app.processEvents()
