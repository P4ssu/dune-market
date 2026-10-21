from datetime import datetime, timedelta, timezone

from dune_market.models import ItemKey, Observation
from dune_market.store_sqlite import SqliteStore

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
KEY = ItemKey("Cobalt Paste", "MISC - REFINEDRESOURCES", "unknown")


def sell(hours_ago, avg, low):
    return Observation(KEY, "sell", NOW - timedelta(hours=hours_ago), "Mari", avg=avg, low=low)


def test_sqlite_roundtrip(tmp_path):
    path = str(tmp_path / "prices.db")
    store = SqliteStore(path)
    store.add([sell(1, 100, 80)])
    reopened = SqliteStore(path)
    (stats,) = reopened.lookup("Cobalt Paste", "MISC - REFINEDRESOURCES", NOW)
    assert (stats.avg, stats.lowest, stats.contributor) == (100, 80, "Mari")


def test_lookup_unknown_item_is_empty(tmp_path):
    assert SqliteStore(str(tmp_path / "p.db")).lookup("Nothing", "X - Y", NOW) == []


def test_recent_sells_newest_first(tmp_path):
    store = SqliteStore(str(tmp_path / "p.db"))
    store.add([sell(5, 100, 80), sell(1, 120, 90), sell(3, 110, 85)])
    assert [s.avg for s in store.recent_sells(KEY, 2)] == [120, 110]


def test_latest_sell_returns_newest(tmp_path):
    store = SqliteStore(str(tmp_path / "p.db"))
    store.add([sell(5, 100, 80), sell(1, 120, 90)])
    assert store.latest_sell(KEY).avg == 120


def test_latest_sell_none_when_missing(tmp_path):
    assert SqliteStore(str(tmp_path / "p.db")).latest_sell(KEY) is None
