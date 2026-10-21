from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image

from dune_market.models import ItemKey, Observation
from dune_market.scanner import Scanner, accept, buy_tab_on_all_grades, observations_from_words, typical_sell
from dune_market.store_sqlite import SqliteStore

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
FABRIC = ItemKey("Atmospheric Filtered Fabric", "MISC - COMPONENTS", "0")


def sell_obs(avg, low=None):
    return Observation(FABRIC, "sell", NOW, "Mari", avg=avg, low=low or avg // 2)


def frame(brightness: int) -> Image.Image:
    return Image.new("RGB", (160, 100), (brightness,) * 3)


def test_sell_screenshot_becomes_sell_observations(shot_words):
    observations = observations_from_words(shot_words("sell"), "Mari", NOW)
    assert len(observations) == 6
    assert all(o.kind == "sell" and o.contributor == "Mari" for o in observations)
    fabric = next(o for o in observations if o.key == FABRIC)  # selected row, panel shows no badge: grade 0
    assert all(o.key.grade == "unknown" for o in observations if o is not fabric)
    assert (fabric.avg, fabric.low) == (56359, 46000)


def with_grade(words, grade):
    """The Buy tab screenshot as if its grade filter showed `grade` instead of ALL."""
    return [replace(w, text=f"GRADE:{grade}") if w.text.upper().startswith("GRADE:") else w for w in words]


def test_buy_tab_on_all_grades_is_not_saved(shot_words):
    assert observations_from_words(shot_words("buy tab"), "Mari", NOW) == []
    assert buy_tab_on_all_grades(shot_words("buy tab")) is True


def test_buy_tab_with_one_grade_is_saved_under_that_grade(shot_words):
    words = with_grade(shot_words("buy tab"), "3")
    observations = observations_from_words(words, "Mari", NOW)
    assert len(observations) == 5
    assert all(o.kind == "buy" and o.key.grade == "3" and o.price == 10_000_000 for o in observations)
    assert buy_tab_on_all_grades(words) is False


def test_my_orders_yields_nothing(shot_words):
    assert observations_from_words(shot_words("my orders tab"), "Mari", NOW) == []


def test_inventory_yields_nothing(shot_words):
    assert observations_from_words(shot_words("item hover"), "Mari", NOW) == []


def test_guard_rejects_big_jump():
    assert accept(sell_obs(4_000), sell_obs(56_359)) is False
    assert accept(sell_obs(400_000), sell_obs(56_359)) is False


def test_guard_accepts_normal_change_and_first_sighting():
    assert accept(sell_obs(60_000), sell_obs(56_359)) is True
    assert accept(sell_obs(4_000), None) is True


def test_guard_accepts_value_seen_twice(shot_words, tmp_path):
    words = [
        replace(w, text="4,000") if w.text.startswith("56,359") else w for w in shot_words("sell")
    ]
    store = SqliteStore(str(tmp_path / "p.db"))
    store.add([sell_obs(56_359, 46_000)])
    scanner = Scanner(store, "Mari", exchange_open=lambda f: True, grab=lambda: frame(10), read=lambda image, offset=(0, 0): words)

    assert scanner.scan_once(NOW) == 0  # first frame: waits for the list to settle
    assert scanner.scan_once(NOW) == 5  # the other five rows; the odd value is held back
    assert store.latest_sell(FABRIC).avg == 56_359
    # The list did not change, but a held-back price makes the scanner read it once more.
    assert scanner.scan_once(NOW + timedelta(seconds=1)) == 6  # seen twice: now accepted
    assert store.latest_sell(FABRIC).avg == 4_000
    assert scanner.scan_once(NOW + timedelta(seconds=2)) == 0  # nothing owed any more: no third read


def test_guard_compares_with_the_median_so_one_stored_misread_does_not_block(shot_words, tmp_path):
    store = SqliteStore(str(tmp_path / "p.db"))
    store.add([sell_obs(56_000, 46_000), sell_obs(57_000, 46_500), replace(sell_obs(560, 460), observed_at=NOW + timedelta(seconds=1))])
    assert accept(sell_obs(56_359, 46_000), typical_sell(store.recent_sells(FABRIC, 5))) is True
    assert typical_sell([]) is None


def test_scan_once_with_black_frame_stores_nothing(tmp_path):
    store = SqliteStore(str(tmp_path / "p.db"))
    scanner = Scanner(store, "Mari", exchange_open=lambda f: True, grab=lambda: Image.new("RGB", (640, 400)))
    assert scanner.scan_once(NOW) == 0


def test_scan_once_when_grab_returns_none(tmp_path):
    scanner = Scanner(SqliteStore(str(tmp_path / "p.db")), "Mari", exchange_open=lambda f: True, grab=lambda: None)
    assert scanner.scan_once(NOW) == 0


def test_scan_once_survives_grab_error(tmp_path):
    def broken():
        raise OSError("no display")

    scanner = Scanner(SqliteStore(str(tmp_path / "p.db")), "Mari", exchange_open=lambda f: True, grab=broken)
    assert scanner.scan_once(NOW) == 0


def test_unchanged_frame_is_not_rescanned(shot_words, tmp_path):
    store = SqliteStore(str(tmp_path / "p.db"))
    words = shot_words("sell")
    scanner = Scanner(store, "Mari", exchange_open=lambda f: True, grab=lambda: frame(10), read=lambda image, offset=(0, 0): words)
    scanner.scan_once(NOW)
    assert scanner.scan_once(NOW) == 6
    assert scanner.scan_once(NOW + timedelta(seconds=1)) == 0


def list_frame(rows: int) -> Image.Image:
    """A list-like frame: `rows` bright bars on a dark background inside the scanned area."""
    image = Image.new("RGB", (1600, 1000), (12, 12, 12))
    for i in range(rows):
        image.paste((200, 190, 160), (100, 200 + i * 80, 1000, 230 + i * 80))
    return image


def test_one_new_row_is_read_even_though_the_rest_of_the_screen_is_the_same(tmp_path):
    reads = []
    frames = iter([list_frame(5), list_frame(5), list_frame(6), list_frame(6)])
    scanner = Scanner(SqliteStore(str(tmp_path / "p.db")), "Mari", exchange_open=lambda f: True, grab=lambda: next(frames),
                      read=lambda image, offset=(0, 0): reads.append(1) or [])
    for _ in range(4):
        scanner.scan_once(NOW)
    assert len(reads) == 2  # the five-row list, then again once the sixth row appeared and settled


def test_a_moving_list_is_read_only_after_it_settles(tmp_path):
    reads = []
    frames = iter([list_frame(1), list_frame(2), list_frame(3), list_frame(4), list_frame(4)])
    scanner = Scanner(SqliteStore(str(tmp_path / "p.db")), "Mari", exchange_open=lambda f: True, grab=lambda: next(frames),
                      read=lambda image, offset=(0, 0): reads.append(1) or [])
    for _ in range(5):
        scanner.scan_once(NOW)
    assert len(reads) == 1  # rows popping in one by one: one read of the finished list


def test_list_that_settles_while_the_exchange_bar_fades_in_is_still_read(tmp_path):
    reads = []
    bar = iter([False, False, True])
    scanner = Scanner(SqliteStore(str(tmp_path / "p.db")), "Mari", exchange_open=lambda f: next(bar), grab=lambda: list_frame(5),
                      read=lambda image, offset=(0, 0): reads.append(1) or [])
    for _ in range(3):
        scanner.scan_once(NOW)
    assert len(reads) == 1  # the old check had already used up this frame while the bar was not yet detected


def test_guard_rejects_low_price_jump():
    assert accept(sell_obs(56_359, low=4_000), sell_obs(56_359, low=46_000)) is False
    assert accept(sell_obs(56_359, low=47_000), sell_obs(56_359, low=46_000)) is True


def test_scanner_does_nothing_while_the_game_is_not_in_front(shot_words, tmp_path):
    calls = []
    scanner = Scanner(SqliteStore(str(tmp_path / "p.db")), "Mari", exchange_open=lambda f: True, grab=lambda: frame(10),
                      read=lambda image, offset=(0, 0): calls.append(1) or shot_words("sell"), active=lambda: False)
    assert scanner.scan_once(NOW) == 0
    assert calls == []


def test_scanner_does_no_ocr_outside_the_exchange(tmp_path):
    calls = []
    scanner = Scanner(SqliteStore(str(tmp_path / "p.db")), "Mari", grab=iter([frame(10), frame(90)]).__next__,
                      read=lambda image, offset=(0, 0), scale=1: calls.append(1) or [])
    assert scanner.scan_once(NOW) == 0
    assert scanner.scan_once(NOW + timedelta(seconds=0.1)) == 0
    assert calls == []  # the pixel check says "no Exchange bar", so nothing is OCR'd


def test_scan_pace_is_slow_until_the_exchange_is_seen(shot_image, tmp_path):
    scanner = Scanner(SqliteStore(str(tmp_path / "p.db")), "Mari", grab=iter([frame(10), shot_image("sell")]).__next__,
                      read=lambda image, offset=(0, 0), scale=1: [])
    scanner.scan_once(NOW)
    assert scanner.idle_delay >= 0.4  # not in the Exchange: check rarely
    scanner.scan_once(NOW + timedelta(seconds=1))
    assert scanner.idle_delay <= 0.15  # Exchange open: scan quickly


def test_scanner_describes_what_it_just_read(shot_words, tmp_path):
    big = Image.new("RGB", (2560, 1600), (10, 10, 10))
    scanner = Scanner(SqliteStore(str(tmp_path / "p.db")), "Mari", exchange_open=lambda f: True, grab=lambda: big,
                      read=lambda image, offset=(0, 0), scale=1: shot_words("sell"))
    scanner.scan_once(NOW)
    scanner.scan_once(NOW)
    assert scanner.last_label == "Sell tab"
    assert scanner.last_rows == 6


def test_scanner_label_for_buy_tab_names_category_and_grade(shot_words, tmp_path):
    big = Image.new("RGB", (2560, 1600), (10, 10, 10))
    scanner = Scanner(SqliteStore(str(tmp_path / "p.db")), "Mari", exchange_open=lambda f: True, grab=lambda: big,
                      read=lambda image, offset=(0, 0), scale=1: with_grade(shot_words("buy tab"), "3"))
    scanner.scan_once(NOW)
    scanner.scan_once(NOW)
    assert scanner.last_label == "Buy tab · GARMENTS - LIGHTARMOR · grade 3"


def test_scanner_saves_nothing_and_says_so_on_all_grades(shot_words, tmp_path):
    big = Image.new("RGB", (2560, 1600), (10, 10, 10))
    store = SqliteStore(str(tmp_path / "p.db"))
    scanner = Scanner(store, "Mari", exchange_open=lambda f: True, grab=lambda: big,
                      read=lambda image, offset=(0, 0), scale=1: shot_words("buy tab"))
    scanner.scan_once(NOW)
    assert scanner.scan_once(NOW) == 0
    assert scanner.skipped_all_grades is True
    assert store.search("helmet", NOW) == [] and store.unsent(10) == []
