"""Turn stored observations into the numbers the popup shows."""

from datetime import datetime, timedelta

from dune_market.models import ItemKey, ItemStats, Observation
from dune_market.ocr import name_key

STALE_AFTER = timedelta(hours=24)
TREND_MIN_AGE = timedelta(hours=12)
TREND_MAX_AGE = timedelta(days=7)
OUTLIER_FACTOR = 20  # a buy listing above this many times the known average is ignored
LOW_OUTLIER_FACTOR = 5  # ...and so is one below 1/5 of it (a likely OCR misread)
SESSION_WINDOW = timedelta(minutes=30)  # buy scans this close together are one scroll through the list


def _ident(key: ItemKey) -> tuple[str, str, str]:
    return name_key(key.name), key.category, key.grade


def compute_stats(key: ItemKey, observations: list[Observation], now: datetime) -> ItemStats | None:
    own = sorted((o for o in observations if _ident(o.key) == _ident(key)), key=lambda o: o.observed_at)
    if not own:
        return None
    sells = [o for o in own if o.kind == "sell"]
    newest_sell = sells[-1] if sells else None
    avg = newest_sell.avg if newest_sell else None

    def plausible(o: Observation) -> bool:
        return not (avg and (o.price > avg * OUTLIER_FACTOR or o.price < avg / LOW_OUTLIER_FACTOR))

    # Buy listings come from scans within the staleness window. The count uses the
    # newest scan only; "cheapest" also looks at the scans of the same scroll session.
    buys = [o for o in own if o.kind == "buy" and now - o.observed_at <= STALE_AFTER]
    newest_buy = buys[-1] if buys else None
    listings: list[int] | None = None
    session: list[int] = []
    if newest_buy:
        listings = [o.price for o in buys if o.observed_at == newest_buy.observed_at and plausible(o)]
        session = [
            o.price for o in buys
            if newest_buy.observed_at - o.observed_at <= SESSION_WINDOW and plausible(o)
        ]

    fresh_sell = newest_sell if newest_sell and now - newest_sell.observed_at <= STALE_AFTER else None
    candidates = ([fresh_sell.low] if fresh_sell and fresh_sell.low is not None else []) + session

    trend = None
    if newest_sell and avg:
        older = [
            s for s in sells
            if s.observed_at <= newest_sell.observed_at - TREND_MIN_AGE and now - s.observed_at <= TREND_MAX_AGE
        ]
        if older and older[-1].avg:
            trend = round((avg - older[-1].avg) / older[-1].avg * 100, 1)

    # The data is as old as the oldest value the popup shows.
    shown = [o for o in (newest_sell, newest_buy) if o] or [own[-1]]
    oldest = min(shown, key=lambda o: o.observed_at)
    return ItemStats(
        key=key,
        avg=avg,
        cheapest=min(candidates) if candidates else None,
        trend_pct=trend,
        listing_count=len(listings) if listings is not None else None,
        updated_at=oldest.observed_at,
        contributor=oldest.contributor,
        stale=now - oldest.observed_at > STALE_AFTER,
    )


def stats_by_grade(observations: list[Observation], now: datetime) -> list[ItemStats]:
    """One ItemStats per item key (grade) in `observations`, newest first."""
    keys = {_ident(o.key): o.key for o in observations}
    stats = [s for s in (compute_stats(k, observations, now) for k in keys.values()) if s]
    return sorted(stats, key=lambda s: s.updated_at, reverse=True)
