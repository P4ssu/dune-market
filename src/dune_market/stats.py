"""Turn stored observations into the numbers the popup shows."""

from datetime import datetime, timedelta

from dune_market.models import ItemKey, ItemStats, Observation

STALE_AFTER = timedelta(hours=24)
TREND_MIN_AGE = timedelta(hours=12)
TREND_MAX_AGE = timedelta(days=7)
OUTLIER_FACTOR = 20  # a buy listing above this many times the known average is ignored


def compute_stats(key: ItemKey, observations: list[Observation], now: datetime) -> ItemStats | None:
    own = sorted((o for o in observations if o.key == key), key=lambda o: o.observed_at)
    if not own:
        return None
    sells = [o for o in own if o.kind == "sell"]
    newest_sell = sells[-1] if sells else None
    avg = newest_sell.avg if newest_sell else None

    # Buy listings come from the newest scan within the staleness window.
    buys = [o for o in own if o.kind == "buy" and now - o.observed_at <= STALE_AFTER]
    listings: list[int] | None = None
    if buys:
        scan_time = max(o.observed_at for o in buys)
        listings = [
            o.price for o in buys
            if o.observed_at == scan_time and not (avg and o.price > avg * OUTLIER_FACTOR)
        ]

    candidates = ([newest_sell.low] if newest_sell and newest_sell.low is not None else []) + (listings or [])

    trend = None
    if newest_sell and avg:
        older = [
            s for s in sells
            if s.observed_at <= newest_sell.observed_at - TREND_MIN_AGE and now - s.observed_at <= TREND_MAX_AGE
        ]
        if older and older[-1].avg:
            trend = round((avg - older[-1].avg) / older[-1].avg * 100, 1)

    newest = own[-1]
    return ItemStats(
        key=key,
        avg=avg,
        cheapest=min(candidates) if candidates else None,
        trend_pct=trend,
        listing_count=len(listings) if listings is not None else None,
        updated_at=newest.observed_at,
        contributor=newest.contributor,
        stale=now - newest.observed_at > STALE_AFTER,
    )


def stats_by_grade(observations: list[Observation], now: datetime) -> list[ItemStats]:
    """One ItemStats per item key (grade) in `observations`, newest first."""
    keys = {o.key for o in observations}
    stats = [s for s in (compute_stats(k, observations, now) for k in keys) if s]
    return sorted(stats, key=lambda s: s.updated_at, reverse=True)
