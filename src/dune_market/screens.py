"""Tell which Exchange tab (if any) is on screen, from header text."""

from dune_market.models import Screen, Word


def _compact(text: str) -> str:
    # The OCR engine often drops spaces ("AVG.PRICE"), so compare without them.
    return "".join(text.split()).upper()


def classify(words: list[Word]) -> Screen:
    texts = [_compact(w.text) for w in words]

    def has(fragment: str) -> bool:
        return any(fragment in t for t in texts)

    if has("AVG.") and has("LOWPRICE"):
        return Screen.SELL
    if (has("QUANTITY") and has("EXPIRATION")) or (has("COMPLETED") and has("ACTIVE")):
        return Screen.MY_ORDERS
    if has("EXPIRATION") and has("CATEGORYFILTER") and not has("QUANTITY"):
        return Screen.BUY
    return Screen.OTHER
