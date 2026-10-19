from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

from dune_market.models import ItemKey, ItemStats, Observation
from dune_market.popup import format_popup, hover_popup
from dune_market.store_sqlite import SqliteStore

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def stats(grade="unknown", avg=12_400, cheapest=9_800, trend=8.0, count=14, hours=2, stale=False, who="Mari"):
    return ItemStats(ItemKey("Maula Pistol Blueprint", "SCHEMATIC - UNIQUE", grade), avg, cheapest, trend, count,
                     NOW - timedelta(hours=hours), who, stale)


def test_popup_full_data():
    assert format_popup("Maula Pistol Blueprint", [stats()], NOW) == [
        "Maula Pistol Blueprint",
        "Grade unknown",
        "Avg price: 12,400 ▲ 8%",
        "Cheapest now: 9,800",
        "Listings: 14",
        "Updated 2 h ago by Mari",
    ]


def test_popup_trend_down_and_flat():
    assert "Avg price: 12,400 ▼ 3%" in format_popup("X", [stats(trend=-3.0)], NOW)
    assert "Avg price: 12,400" in format_popup("X", [stats(trend=None)], NOW)


def test_popup_stale_marked_old():
    lines = format_popup("X", [stats(hours=30, stale=True)], NOW)
    assert lines[-1] == "Updated 1 d ago by Mari (old)"


def test_popup_omits_missing_listing_count():
    assert not any(line.startswith("Listings") for line in format_popup("X", [stats(count=None)], NOW))


def test_popup_no_data():
    assert format_popup("Unknown Thing", [], NOW) == ["Unknown Thing", "No price data yet"]


def test_popup_grade_known_label():
    assert "Grade: 3" in format_popup("X", [stats(grade="3")], NOW)


def test_popup_multiple_grades_listed():
    lines = format_popup("X", [stats(grade="3", avg=500), stats(grade="unknown", avg=400)], NOW)
    assert lines.count("Grade: 3") == 1 and lines.count("Grade unknown") == 1
    assert lines.index("Grade: 3") < lines.index("Grade unknown")


def test_popup_minutes_ago():
    lines = format_popup("X", [replace_updated(stats(), minutes=5)], NOW)
    assert lines[-1] == "Updated 5 min ago by Mari"


def replace_updated(s, minutes):
    from dataclasses import replace

    return replace(s, updated_at=NOW - timedelta(minutes=minutes))


# --- hover_popup: frame + cursor -> popup lines and position -------------------------------

BLACK = Image.new("RGB", (2559, 1599))


def fake_reader(words):
    """Pretend OCR: return the known words that fall inside the requested crop."""

    def read(image, offset=(0, 0), scale=1):
        ox, oy = offset
        return [w for w in words if ox <= w.x < ox + image.width / scale and oy <= w.y < oy + image.height / scale]

    return read


def dust_store(tmp_path):
    store = SqliteStore(str(tmp_path / "p.db"))
    key = ItemKey("Spice-infused Plastanium Dust", "MISC - COMPONENTS", "unknown")
    store.add([Observation(key, "sell", NOW - timedelta(hours=1), "Mari", avg=5_000, low=4_000)])
    return store


def test_hover_popup_shows_stats(shot_words, shot_image, tmp_path):
    popup = hover_popup(shot_image("item hover"), (842, 927), dust_store(tmp_path), NOW, fake_reader(shot_words("item hover")))
    assert popup.lines[0] == "Spice-infused Plastanium Dust"
    assert "Avg price: 5,000" in popup.lines
    assert popup.y < 851  # placed above the tooltip banner, whose top border is at y=851


def test_hover_popup_no_data_yet(shot_words, shot_image, tmp_path):
    popup = hover_popup(shot_image("schematic hover"), (531, 620), dust_store(tmp_path), NOW, fake_reader(shot_words("schematic hover")))
    assert popup.lines == ["Quick-release Trigger", "No price data yet"]


def test_hover_popup_none_on_exchange_tab(shot_words, shot_image, tmp_path):
    from dune_market.banner import find_banner

    sell = shot_image("sell")
    assert find_banner(sell, (2000, 500)) is not None  # the detail panel title banner: the check below is really exercised
    assert hover_popup(sell, (2000, 500), dust_store(tmp_path), NOW, fake_reader(shot_words("sell"))) is None


def test_hover_popup_none_without_tooltip_costs_no_ocr(tmp_path):
    calls = []
    assert hover_popup(BLACK, (500, 500), dust_store(tmp_path), NOW, lambda image, offset=(0, 0), scale=1: calls.append(1) or []) is None
    assert calls == []


def test_hover_popup_none_without_frame(tmp_path):
    assert hover_popup(None, (500, 500), dust_store(tmp_path), NOW, fake_reader([])) is None


def test_hover_popup_real_ocr_reads_the_full_name(tmp_path):
    """A crop that cuts the tooltip header would truncate the name (seen with real OCR)."""
    import pytest

    from dune_market.ocr import read_words

    path = Path(__file__).resolve().parent.parent / "screenshots" / "item hover.png"
    if not path.exists():
        pytest.skip("missing screenshot item hover.png")
    popup = hover_popup(Image.open(path).convert("RGB"), (842, 927), dust_store(tmp_path), NOW, read_words)
    assert popup.lines[0] == "Spice-infused Plastanium Dust"
    assert "Avg price: 5,000" in popup.lines


def test_hover_popup_ocrs_only_small_crops(shot_words, shot_image, tmp_path):
    """Only the tooltip banner is OCR'd, never a large area (so never the character name or Solari balance)."""
    calls = []
    inner = fake_reader(shot_words("item hover"))

    def recording(image, offset=(0, 0), scale=1):
        calls.append((offset, (image.width / scale, image.height / scale)))
        return inner(image, offset, scale)

    image = shot_image("item hover")
    assert hover_popup(image, (842, 927), dust_store(tmp_path), NOW, recording) is not None
    assert calls
    assert all(w * h < 0.03 * image.width * image.height for _, (w, h) in calls)


def test_hover_popup_skips_the_tab_bar_ocr_when_told_the_exchange_is_closed(shot_words, shot_image, tmp_path):
    calls = []
    inner = fake_reader(shot_words("item hover"))

    def recording(image, offset=(0, 0), scale=1):
        calls.append(offset)
        return inner(image, offset, scale)

    popup = hover_popup(shot_image("item hover"), (842, 927), dust_store(tmp_path), NOW, recording, exchange_open=lambda frame: False)
    assert popup is not None
    assert all(y > 0 for _, y in calls)  # nothing from the top strip


def test_hover_popup_remembers_what_it_read_from_a_banner(shot_words, shot_image, tmp_path):
    calls = []
    inner = fake_reader(shot_words("item hover"))

    def recording(image, offset=(0, 0), scale=1):
        calls.append(offset)
        return inner(image, offset, scale)

    image, cache = shot_image("item hover"), {}
    store = dust_store(tmp_path)
    first = hover_popup(image, (842, 927), store, NOW, recording, exchange_open=lambda f: False, header_cache=cache)
    reads_for_first = len(calls)
    second = hover_popup(image, (842, 927), store, NOW, recording, exchange_open=lambda f: False, header_cache=cache)
    assert reads_for_first > 0 and len(calls) == reads_for_first  # the second hover needed no OCR
    assert first.lines == second.lines


def test_hover_popup_carries_the_banner_rectangle(shot_words, shot_image, tmp_path):
    popup = hover_popup(shot_image("item hover"), (842, 927), dust_store(tmp_path), NOW, fake_reader(shot_words("item hover")))
    x, y, w, h = popup.anchor
    assert abs(x - 980) <= 4 and abs(y - 852) <= 4 and 580 <= w <= 620
