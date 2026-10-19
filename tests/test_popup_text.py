from datetime import datetime, timedelta, timezone

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

FRAME = Image.new("RGB", (2559, 1599))


def fake_reader(words):
    """Pretend OCR: return the known words that fall inside the requested crop."""

    def read(image, offset=(0, 0)):
        ox, oy = offset
        return [w for w in words if ox <= w.x < ox + image.width and oy <= w.y < oy + image.height]

    return read


def dust_store(tmp_path):
    store = SqliteStore(str(tmp_path / "p.db"))
    key = ItemKey("Spice-infused Plastanium Dust", "MISC - COMPONENTS", "unknown")
    store.add([Observation(key, "sell", NOW - timedelta(hours=1), "Mari", avg=5_000, low=4_000)])
    return store


def test_hover_popup_shows_stats(shot_words, tmp_path):
    popup = hover_popup(FRAME, (842, 927), dust_store(tmp_path), NOW, fake_reader(shot_words("item hover")))
    assert popup.lines[0] == "Spice-infused Plastanium Dust"
    assert "Avg price: 5,000" in popup.lines
    assert popup.y < 861  # placed above the tooltip header, which sits at y=861


def test_hover_popup_no_data_yet(shot_words, tmp_path):
    popup = hover_popup(FRAME, (531, 620), dust_store(tmp_path), NOW, fake_reader(shot_words("schematic hover")))
    assert popup.lines == ["Quick-release Trigger", "No price data yet"]


def test_hover_popup_none_on_exchange_tab(shot_words, tmp_path):
    popup = hover_popup(FRAME, (500, 480), dust_store(tmp_path), NOW, fake_reader(shot_words("sell")))
    assert popup is None


def test_hover_popup_none_without_tooltip(tmp_path):
    assert hover_popup(FRAME, (500, 500), dust_store(tmp_path), NOW, fake_reader([])) is None


def test_hover_popup_none_without_frame(tmp_path):
    assert hover_popup(None, (500, 500), dust_store(tmp_path), NOW, fake_reader([])) is None
