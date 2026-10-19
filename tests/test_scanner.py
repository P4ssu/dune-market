from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image

from dune_market.models import ItemKey, Observation
from dune_market.scanner import Scanner, accept, observations_from_words
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


def test_buy_all_grade_is_unknown(shot_words):
    observations = observations_from_words(shot_words("buy tab"), "Mari", NOW)
    assert len(observations) == 5
    assert all(o.kind == "buy" and o.key.grade == "unknown" and o.price == 10_000_000 for o in observations)


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
    frames = iter([frame(10), frame(60)])
    scanner = Scanner(store, "Mari", exchange_open=lambda f: True, grab=lambda: next(frames), read=lambda image, offset=(0, 0): words)

    assert scanner.scan_once(NOW) == 5  # the other five rows; the odd value is held back
    assert store.latest_sell(FABRIC).avg == 56_359
    assert scanner.scan_once(NOW + timedelta(seconds=1)) == 6  # seen twice: now accepted
    assert store.latest_sell(FABRIC).avg == 4_000


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
    assert scanner.scan_once(NOW) == 6
    assert scanner.scan_once(NOW + timedelta(seconds=1)) == 0


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
    assert scanner.last_label == "Sell tab"
    assert scanner.last_rows == 6


def test_scanner_label_for_buy_tab_names_category_and_grade(shot_words, tmp_path):
    big = Image.new("RGB", (2560, 1600), (10, 10, 10))
    scanner = Scanner(SqliteStore(str(tmp_path / "p.db")), "Mari", exchange_open=lambda f: True, grab=lambda: big,
                      read=lambda image, offset=(0, 0), scale=1: shot_words("buy tab"))
    scanner.scan_once(NOW)
    assert scanner.last_label == "Buy tab · GARMENTS - LIGHTARMOR · all grades"
