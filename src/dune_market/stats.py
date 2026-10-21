"""Turn stored observations into the numbers the popup shows."""

import statistics
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
    """The last known prices of one item key (grade), however old they are.

    "Lowest" is the cheapest price of the newest scan session only (the Sell tab LOW and Buy tab rows
    read within SESSION_WINDOW of the newest observation), so an older low price does not hide today's
    price.
    """
    own = sorted((o for o in observations if _ident(o.key) == _ident(key)), key=lambda o: o.observed_at)
    if not own:
        return None
    latest = own[-1].observed_at

    def recent(o: Observation | None) -> bool:
        return o is not None and latest - o.observed_at <= STALE_AFTER

    sells = [o for o in own if o.kind == "sell"]
    newest_sell = sells[-1] if sells else None
    avg = newest_sell.avg if newest_sell else None

    def plausible(o: Observation) -> bool:
        return not (avg and (o.price > avg * OUTLIER_FACTOR or o.price < avg / LOW_OUTLIER_FACTOR))

    # The count uses the newest Buy scan only; lowest and highest also look at the scans of the same
    # scroll session (one scan sees about five rows of a longer list).
    buys = [o for o in own if o.kind == "buy"]
    newest_buy = buys[-1] if recent(buys[-1] if buys else None) else None
    listings: list[int] | None = None
    session_rows: list[Observation] = []
    if newest_buy:
        listings = [o.price for o in buys if o.observed_at == newest_buy.observed_at and plausible(o)]
        session_rows = [
            o for o in buys
            if newest_buy.observed_at - o.observed_at <= SESSION_WINDOW and plausible(o)
        ]
    session = [o.price for o in session_rows]

    shown_sell = newest_sell if recent(newest_sell) and newest_sell.low is not None else None

    def in_last_session(o: Observation | None) -> bool:
        return o is not None and latest - o.observed_at <= SESSION_WINDOW

    lows = ([shown_sell.low] if in_last_session(shown_sell) else []) + (session if in_last_session(newest_buy) else [])
    lowest = min(lows) if lows else None
    # The Buy listing with that price (the newest of equal ones), for its expiry time.
    cheapest_row = max(
        (o for o in session_rows if o.price == lowest and o.expires_in_s is not None and in_last_session(newest_buy)),
        key=lambda o: o.observed_at, default=None,
    )

    # Trend of the Sell tab's low price against a scan at least TREND_MIN_AGE older; only shown when that
    # low price is part of the last session, so the arrow belongs to the number next to it.
    trend = None
    if in_last_session(shown_sell) and shown_sell.low:
        older = [
            s for s in sells
            if s.low and s.observed_at <= shown_sell.observed_at - TREND_MIN_AGE and now - s.observed_at <= TREND_MAX_AGE
        ]
        if older:
            trend = round((shown_sell.low - older[-1].low) / older[-1].low * 100, 1)

    # Without a Sell scan the game's average is unknown; the mean of the listings seen stands in for it.
    # Listings far from their median (joke prices, misreads) are left out so one of them cannot drag it.
    listing_avg = None
    if avg is None and session:
        middle = statistics.median(session)
        usual = [p for p in session if middle / LOW_OUTLIER_FACTOR <= p <= middle * LOW_OUTLIER_FACTOR]
        listing_avg = round(statistics.mean(usual))

    # The data is as old as the oldest value the popup shows.
    shown = [o for o in (shown_sell, newest_buy if session else None) if o] or [own[-1]]
    oldest = min(shown, key=lambda o: o.observed_at)
    return ItemStats(
        key=key,
        lowest=lowest,
        highest=max(session) if session else None,
        trend_pct=trend,
        listing_count=len(listings) if listings is not None else None,
        updated_at=oldest.observed_at,
        contributor=oldest.contributor,
        stale=now - oldest.observed_at > STALE_AFTER,
        avg=avg if avg is not None else listing_avg,
        avg_at=newest_sell.observed_at if newest_sell else None,
        avg_from_listings=listing_avg is not None,
        lowest_expires_at=cheapest_row.observed_at + timedelta(seconds=cheapest_row.expires_in_s) if cheapest_row else None,
    )


def stats_by_grade(observations: list[Observation], now: datetime) -> list[ItemStats]:
    """One ItemStats per item key (grade) in `observations`, newest first."""
    keys = {_ident(o.key): o.key for o in observations}
    stats = [s for s in (compute_stats(k, observations, now) for k in keys.values()) if s]
    return sorted(stats, key=lambda s: s.updated_at, reverse=True)
