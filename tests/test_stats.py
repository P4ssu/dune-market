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


def test_lowest_uses_lower_of_sell_low_and_buy():
    stats = compute_stats(KEY, [sell(1, 100, 80), buy(1, 70), buy(1, 95)], NOW)
    assert stats.lowest == 70
    stats = compute_stats(KEY, [sell(1, 100, 60), buy(1, 70)], NOW)
    assert stats.lowest == 60


def test_highest_is_the_most_expensive_buy_listing():
    stats = compute_stats(KEY, [sell(1, 100, 80), buy(1, 70), buy(1, 95)], NOW)
    assert stats.highest == 95


def test_last_known_average_is_kept_with_its_own_age():
    stats = compute_stats(KEY, [sell(120, 8_900, 8_900), buy(0.02, 15_000)], NOW)
    assert (stats.avg, stats.avg_at) == (8_900, NOW - timedelta(hours=120))


def test_without_sell_scan_the_average_comes_from_the_listings_seen():
    stats = compute_stats(KEY, [buy(1, 100), buy(1, 200), buy(1, 300), buy(1, 9_000_000)], NOW)
    assert (stats.avg, stats.avg_from_listings) == (200, True)  # the joke price is left out


def test_the_games_average_wins_over_the_listings():
    stats = compute_stats(KEY, [sell(1, 150, 90), buy(1, 100), buy(1, 300)], NOW)
    assert (stats.avg, stats.avg_from_listings) == (150, False)


def test_last_lowest_is_from_the_newest_scan_session_only():
    stats = compute_stats(KEY, [sell(20, 100, 50), buy(0.1, 90), buy(0.1, 95)], NOW)
    assert stats.lowest == 90  # the Sell low from 20 h ago is not "last" any more
    assert (stats.all_time_low, stats.all_time_low_at) == (50, NOW - timedelta(hours=20))


def test_no_trend_arrow_when_the_last_lowest_is_not_the_sell_low():
    stats = compute_stats(KEY, [sell(24, 100, 80), sell(2, 150, 88), buy(0.1, 95)], NOW)
    assert stats.trend_pct is None


def test_all_time_low_ignores_misread_listings():
    stats = compute_stats(KEY, [buy(48, 1_000), buy(48, 1_100), buy(48, 9), buy(1, 1_200)], NOW)
    assert stats.all_time_low == 1_000
    assert stats.lowest == 1_200


def test_highest_unknown_without_buy_scan():
    assert compute_stats(KEY, [sell(1, 100, 80)], NOW).highest is None


def test_last_known_prices_are_kept_when_old():
    stats = compute_stats(KEY, [buy(72, 70), buy(72, 95)], NOW)
    assert (stats.lowest, stats.highest, stats.listing_count) == (70, 95, 2)
    assert stats.stale is True


def test_listing_count_from_newest_buy_scan():
    stats = compute_stats(KEY, [buy(5, 70), buy(5, 71), buy(2, 72), buy(2, 73), buy(2, 74)], NOW)
    assert stats.listing_count == 3


def test_listing_count_none_without_buy_scan():
    assert compute_stats(KEY, [sell(1, 100, 80)], NOW).listing_count is None


def test_trend_of_the_low_price_up_ten_percent():
    stats = compute_stats(KEY, [sell(24, 100, 80), sell(0, 150, 88)], NOW)
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
    assert stats.lowest == 9_000
    assert stats.highest == 9_500
    assert stats.listing_count == 1


def test_no_observations_gives_none():
    assert compute_stats(KEY, [], NOW) is None


def test_stats_by_grade_one_entry_per_grade_newest_first():
    g3 = ItemKey("Cobalt Paste", "MISC - REFINEDRESOURCES", "3")
    result = stats_by_grade([sell(5, 100, 80), sell(1, 200, 150, key=g3)], NOW)
    assert [s.key.grade for s in result] == ["3", "unknown"]


def test_buy_price_far_below_average_is_ignored():
    stats = compute_stats(KEY, [sell(1, 10_000, 9_000), buy(1, 1_000), buy(1, 9_500)], NOW)
    assert stats.lowest == 9_000
    assert stats.listing_count == 1


def test_old_sell_low_does_not_undercut_a_fresh_buy_scan():
    stats = compute_stats(KEY, [sell(120, 8_900, 8_900), buy(0.02, 15_000)], NOW)
    assert stats.lowest == 15_000
    assert stats.stale is False
    assert stats.updated_at == NOW - timedelta(hours=0.02)


def test_cheapest_spans_a_scroll_session_but_not_old_scans():
    obs = [buy(2, 50), buy(0.17, 100), buy(0.02, 200), buy(0.02, 210)]  # scans 2 h, 10 min, 1 min ago
    stats = compute_stats(KEY, obs, NOW)
    assert stats.lowest == 100  # the 2 h old scan is outside the session window
    assert stats.highest == 210
    assert stats.listing_count == 2  # count still comes from the newest scan only
