"""Grades read from the screen, name matching and hover timing."""

import sqlite3
from datetime import datetime, timedelta, timezone

from PIL import Image

from dune_market.models import ItemKey, Observation, Word
from dune_market.ocr import find_grade_badge, name_key
from dune_market.parse_sell import parse_sell
from dune_market.parse_tooltip import find_tooltip
from dune_market.popup import HoverTracker, PopupData, hover_popup
from dune_market.scanner import Scanner
from dune_market.store_sqlite import SqliteStore

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
FRAME = Image.new("RGB", (2559, 1599))


def fake_reader(words):
    def read(image, offset=(0, 0)):
        ox, oy = offset
        return [w for w in words if ox <= w.x < ox + image.width and oy <= w.y < oy + image.height]

    return read


# --- OCR helpers ----------------------------------------------------------------------------


def test_name_key_ignores_spaces_case_and_punctuation():
    assert name_key("Robeofthe Sisterhood") == name_key("Robe of the Sisterhood")
    assert name_key("Spice-infused Plastanium Dust") == "spiceinfusedplastaniumdust"


def test_find_grade_badge_reads_digit_at_the_end_of_the_header_line():
    cat = Word("SCHEMATIC-UNIQUE", 689, 353, 241, 20)
    name = Word("Quick-releaseTrigger", 688, 371, 270, 26)
    words = [cat, name, Word("1", 1267, 364, 12, 22)]
    assert find_grade_badge(words, cat, name.x + name.w, name.y + name.h / 2) == "1"


def test_find_grade_badge_is_zero_without_a_badge():
    cat = Word("SCHEMATIC-UNIQUE", 377, 244, 245, 20)
    name = Word("Mendek's Gauntlets", 377, 267, 250, 22)
    elsewhere = Word("1", 420, 600, 12, 22)  # a digit elsewhere on screen is not the badge
    assert find_grade_badge([cat, name, elsewhere], cat, name.x + name.w, name.y + name.h / 2) == "0"


# --- grades on screen ---------------------------------------------------------------------


# The badge is a tiny glyph; it is read from the tight header crop (the popup's second OCR pass).


def test_tooltip_grade_from_badge(shot_crop):
    words = shot_crop("schematic hover", (659, 343, 1457, 443))
    assert find_tooltip(words, (531, 620)).grade == "1"


def test_tooltip_grade_zero_without_badge(shot_crop):
    assert find_tooltip(shot_crop("blueprint hover", (347, 234, 1145, 334)), (223, 620)).grade == "0"
    assert find_tooltip(shot_crop("item hover", (968, 855, 1766, 955)), (842, 927)).grade == "0"


def test_selected_sell_row_gets_its_grade_from_the_detail_panel(shot_words):
    rows = {r.name: r for r in parse_sell(shot_words("sell"))}
    assert rows["Atmospheric Filtered Fabric"].grade == "0"  # the selected panel shows no badge: grade 0
    assert rows["Calibrated Servok"].grade is None  # not selected: its grade is not visible


def test_panel_badge_sets_the_grade():
    words = [
        Word("QUANTITY", 1077, 357, 137, 29), Word("AVG.PRICE", 1316, 357, 144, 29), Word("LOW PRICE", 1557, 357, 144, 29),
        Word("MISC-COMPONENTS", 288, 423, 244, 22), Word("Cobalt Paste", 286, 465, 164, 32),
        Word("19,283", 1322, 462, 106, 27), Word("8,900", 1571, 460, 94, 31),
        Word("MISC-COMPONENTS", 1855, 256, 246, 26), Word("Cobalt Paste", 1855, 281, 200, 29), Word("4", 2435, 273, 15, 20),
    ]
    (row,) = parse_sell(words)
    assert (row.name, row.grade) == ("Cobalt Paste", "4")


# --- scanner region and progress --------------------------------------------------------------


def test_scanner_reads_only_the_list_region_and_reports_progress(shot_words, tmp_path):
    calls = []
    words = shot_words("sell")

    def read(image, offset=(0, 0)):
        calls.append((offset, image.size))
        return words

    big = Image.new("RGB", (2560, 1600), (10, 10, 10))
    scanner = Scanner(SqliteStore(str(tmp_path / "p.db")), "Mari", grab=lambda: big, read=read)
    scanner.scan_once(NOW)
    assert len(calls) == 3  # tab bar strip, the list, then the detail panel title on the Sell tab
    (sx, sy), (sw, sh) = calls[0]
    assert sx > 300 and sx + sw < 2560 - 300 and sy == 0  # strip in the centre: no character name or Solari balance
    (x, y), (w, h) = calls[1]
    assert x > 0 and y > 150 and w < 2560 and y + h < 1500  # the list, without the corners
    assert (scanner.last_new, scanner.session_total) == (6, 6)
    (px, py), (pw, ph) = calls[2]
    assert px > 0.6 * 2560 and py < 0.25 * 1600 and ph < 200  # a tight crop of the panel title


# --- hover: grade choice, name matching, timing ------------------------------------------------


def schematic_reader(shot_words, shot_crop):
    """Pretend OCR for the schematic screenshot: big crops see the frame, the tight header crop sees the badge."""
    full = fake_reader(shot_words("schematic hover"))
    header = shot_crop("schematic hover", (659, 343, 1457, 443))

    def read(image, offset=(0, 0)):
        return header if image.height <= 120 else full(image, offset)

    return read


def _grade_store(tmp_path, *observations):
    store = SqliteStore(str(tmp_path / "p.db"))
    store.add(list(observations))
    return store


NAME, CAT = "Quick-release Trigger", "SCHEMATIC - UNIQUE"


def test_hover_grade_selects_the_matching_stats_block(shot_words, shot_crop, tmp_path):
    store = _grade_store(
        tmp_path,
        Observation(ItemKey(NAME, CAT, "1"), "sell", NOW - timedelta(hours=1), "Mari", avg=700, low=600),
        Observation(ItemKey(NAME, CAT, "unknown"), "buy", NOW - timedelta(hours=1), "Mari", price=500, expires_in_s=100),
    )
    popup = hover_popup(FRAME, (531, 620), store, NOW, schematic_reader(shot_words, shot_crop))
    assert "Grade: 1" in popup.lines and "Avg price: 700" in popup.lines
    assert "Grade unknown" not in popup.lines  # the exact grade wins


def test_hover_grade_falls_back_to_unknown_grade_stats(shot_words, shot_crop, tmp_path):
    store = _grade_store(
        tmp_path,
        Observation(ItemKey(NAME, CAT, "unknown"), "buy", NOW - timedelta(hours=1), "Mari", price=500, expires_in_s=100),
    )
    popup = hover_popup(FRAME, (531, 620), store, NOW, schematic_reader(shot_words, shot_crop))
    assert "Grade unknown" in popup.lines and "Cheapest now: 500" in popup.lines


def test_hover_grade_lists_other_grades_when_nothing_else_matches(shot_words, shot_crop, tmp_path):
    store = _grade_store(
        tmp_path,
        Observation(ItemKey(NAME, CAT, "3"), "buy", NOW - timedelta(hours=1), "Mari", price=900, expires_in_s=100),
    )
    popup = hover_popup(FRAME, (531, 620), store, NOW, schematic_reader(shot_words, shot_crop))
    assert "Grade: 3" in popup.lines


def test_lookup_matches_names_the_ocr_spelled_differently(tmp_path):
    store = _grade_store(
        tmp_path,
        Observation(ItemKey("Robeofthe Sisterhood", "GARMENTS - LIGHTARMOR", "3"), "buy", NOW - timedelta(hours=1), "Mari",
                    price=500, expires_in_s=100),
    )
    (stats,) = store.lookup("Robe of the Sisterhood", "GARMENTS - LIGHTARMOR", NOW)
    assert stats.cheapest == 500


def test_two_spellings_of_one_item_make_one_stats_block(tmp_path):
    store = _grade_store(
        tmp_path,
        Observation(ItemKey("Robeofthe Sisterhood", "G - L", "3"), "buy", NOW - timedelta(hours=2), "Mari", price=500, expires_in_s=1),
        Observation(ItemKey("Robe of the Sisterhood", "G - L", "3"), "buy", NOW - timedelta(hours=1), "Jaan", price=450, expires_in_s=1),
    )
    assert len(store.lookup("Robe of the Sisterhood", "G - L", NOW)) == 1


def test_old_database_without_name_key_is_migrated(tmp_path):
    path = str(tmp_path / "old.db")
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE observations (name TEXT NOT NULL, category TEXT NOT NULL, grade TEXT NOT NULL, kind TEXT NOT NULL,"
        " observed_at TEXT NOT NULL, contributor TEXT NOT NULL, avg INTEGER, low INTEGER, price INTEGER, expires_in_s INTEGER)"
    )
    db.execute(
        "INSERT INTO observations VALUES ('Cobalt Paste','MISC - REFINEDRESOURCES','unknown','sell',?,'Mari',100,80,NULL,NULL)",
        ((NOW - timedelta(hours=1)).isoformat(),),
    )
    db.commit()
    db.close()
    (stats,) = SqliteStore(path).lookup("Cobalt Paste", "MISC - REFINEDRESOURCES", NOW)
    assert stats.avg == 100


def test_popup_is_not_shown_if_the_cursor_moved_during_the_lookup():
    events = []
    positions = iter([(400, 400)])
    tracker = HoverTracker(
        lambda pos: PopupData(["Item"], 1, 1),
        on_show=lambda p: events.append("show"),
        on_hide=lambda: events.append("hide"),
        current_cursor=lambda: next(positions),
    )
    tracker.tick((100, 100), 0.0)
    tracker.tick((100, 100), 0.5)
    assert events == []  # the lookup ran, but the cursor had already left
