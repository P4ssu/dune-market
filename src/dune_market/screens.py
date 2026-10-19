"""Tell which Exchange tab (if any) is on screen, from header text."""

from collections.abc import Callable

from PIL import Image

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


HEADER_BAND = 0.12  # top fraction of the frame holding the Exchange tab names
HEADER_X = (0.35, 0.65)  # ...and the centre part of it; the corners hold the character name and Solari balance


def exchange_tab_open(frame: Image.Image, read: Callable[[Image.Image, tuple[int, int]], list[Word]]) -> bool:
    """True when the Exchange tab bar (BUY / SELL / MY ORDERS) is on screen; reads only a small strip."""
    width, height = frame.size
    left = int(width * HEADER_X[0])
    strip = frame.crop((left, 0, int(width * HEADER_X[1]), int(height * HEADER_BAND)))
    return any("MYORDERS" in _compact(w.text) for w in read(strip, (left, 0)))
