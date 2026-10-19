"""The game draws a 16:9 picture; on a 16:10 monitor it sits between black bars. Positions must not depend on that."""

from PIL import Image

from dune_market.banner import find_banner
from dune_market.layout import content_box
from dune_market.popup import hover_popup
from dune_market.scanner import Scanner
from dune_market.screens import exchange_tab_open
from dune_market.store_sqlite import SqliteStore
from datetime import datetime, timezone

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def test_content_box_skips_black_bars(shot_image):
    left, top, right, bottom = content_box(shot_image("sell"))
    assert (left, right) == (0, 2559) or (left, right) == (0, 2560)
    assert abs(top - 80) <= 8 and abs(bottom - 1520) <= 8


def test_content_box_is_the_whole_frame_without_bars(friend_frame):
    assert content_box(friend_frame("sell")) == (0, 0, 1920, 1080)


def test_content_box_falls_back_to_the_whole_frame_for_dark_or_plain_frames():
    assert content_box(Image.new("RGB", (1920, 1080))) == (0, 0, 1920, 1080)
    assert content_box(Image.new("RGB", (1920, 1080), (30, 30, 30))) == (0, 0, 1920, 1080)


def test_exchange_bar_found_without_black_bars(friend_frame):
    for name in ("sell", "buy tab", "my orders tab"):
        assert exchange_tab_open(friend_frame(name)) is True, name
    assert exchange_tab_open(friend_frame("item hover")) is False


def test_banner_found_without_black_bars(friend_frame):
    banner = find_banner(friend_frame("item hover"), (int(842 * 0.75), int((927 - 80) * 0.75)))
    assert banner is not None and 430 <= banner.w <= 470


def test_scanner_reads_the_sell_tab_on_a_frame_without_black_bars(friend_frame, tmp_path):
    frame = friend_frame("sell")
    scanner = Scanner(SqliteStore(str(tmp_path / "p.db")), "Friend", grab=lambda: frame)
    assert scanner.scan_once(NOW) >= 5
    assert scanner.last_label == "Sell tab"


def test_scanner_reads_the_buy_tab_on_a_frame_without_black_bars(friend_frame, tmp_path):
    frame = friend_frame("buy tab")
    scanner = Scanner(SqliteStore(str(tmp_path / "p.db")), "Friend", grab=lambda: frame)
    assert scanner.scan_once(NOW) >= 4
    assert scanner.last_label.startswith("Buy tab")


def test_hover_popup_works_on_a_frame_without_black_bars(friend_frame, tmp_path):
    popup = hover_popup(friend_frame("item hover"), (int(842 * 0.75), int((927 - 80) * 0.75)), SqliteStore(str(tmp_path / "p.db")), NOW)
    assert popup is not None and popup.lines[0] == "Spice-infused Plastanium Dust"
