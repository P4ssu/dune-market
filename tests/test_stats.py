from datetime import datetime, timedelta, timezone

from dune_market.models import ItemKey, Observation
from dune_market.stats import compute_stats, stats_by_grade

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
KEY = ItemKey("Cobalt Paste", "MISC - REFINEDRESOURCES", "unknown")


def sell(hours_ago, avg, low, contributor="Mari", key=KEY):
    return Observation(key, "sell", NOW - timedelta(hours=hours_ago), contributor, avg=avg, low=low)


def buy(hours_ago, price, key=KEY):
    return Observation(key, "buy", NOW - timedelta(hours=hours_ago), "Mari", price=price, expires_in_s=3600)


def test_avg_is_newest_sell():
    stats = compute_stats(KEY, [sell(5, 100, 80), sell(1, 120, 90)], NOW)
    assert stats.avg == 120


def test_cheapest_uses_lower_of_sell_low_and_buy():
    stats = compute_stats(KEY, [sell(1, 100, 80), buy(1, 70), buy(1, 95)], NOW)
    assert stats.cheapest == 70
    stats = compute_stats(KEY, [sell(1, 100, 60), buy(1, 70)], NOW)
    assert stats.cheapest == 60


def test_listing_count_from_newest_buy_scan():
    stats = compute_stats(KEY, [buy(5, 70), buy(5, 71), buy(2, 72), buy(2, 73), buy(2, 74)], NOW)
    assert stats.listing_count == 3


def test_listing_count_none_without_buy_scan():
    assert compute_stats(KEY, [sell(1, 100, 80)], NOW).listing_count is None


def test_trend_up_ten_percent():
    stats = compute_stats(KEY, [sell(24, 100, 80), sell(0, 110, 90)], NOW)
    assert stats.trend_pct == 10.0


def test_trend_none_without_older_data():
    stats = compute_stats(KEY, [sell(2, 100, 80), sell(0, 110, 90)], NOW)
    assert stats.trend_pct is None


def test_stale_after_24_hours():
    assert compute_stats(KEY, [sell(25, 100, 80)], NOW).stale is True
    assert compute_stats(KEY, [sell(1, 100, 80)], NOW).stale is False


def test_updated_by_newest_contributor():
    stats = compute_stats(KEY, [sell(5, 100, 80, "Mari"), sell(1, 100, 80, "Jaan")], NOW)
    assert stats.contributor == "Jaan"
    assert stats.updated_at == NOW - timedelta(hours=1)


def test_buy_outlier_ignored():
    stats = compute_stats(KEY, [sell(1, 10_000, 9_000), buy(1, 10_000_000), buy(1, 9_500)], NOW)
    assert stats.cheapest == 9_000
    assert stats.listing_count == 1


def test_no_observations_gives_none():
    assert compute_stats(KEY, [], NOW) is None


def test_stats_by_grade_one_entry_per_grade_newest_first():
    g3 = ItemKey("Cobalt Paste", "MISC - REFINEDRESOURCES", "3")
    result = stats_by_grade([sell(5, 100, 80), sell(1, 200, 150, key=g3)], NOW)
    assert [s.key.grade for s in result] == ["3", "unknown"]
