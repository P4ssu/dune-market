"""Tell which Exchange tab (if any) is on screen, from header text."""

import numpy as np
from PIL import Image

from dune_market.banner import gold_mask
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


# The Exchange tab bar has a Q and an E key box (gold squares) at fixed spots; the inventory bar and
# every other screen have them elsewhere or not at all. Fractions of the frame (left, top, right, bottom).
_KEY_BOXES = ((0.368, 0.068, 0.402, 0.116), (0.598, 0.068, 0.632, 0.116))
_MIN_GOLD = 0.12  # measured: Exchange 0.18-0.19, inventory 0.00-0.07, other screens 0.00


def exchange_tab_open(frame: Image.Image) -> bool:
    """True when the Exchange tab bar (BUY / SELL / MY ORDERS) is on screen. Pixels only: about a millisecond."""
    width, height = frame.size
    for left, top, right, bottom in _KEY_BOXES:
        box = np.asarray(frame.crop((int(width * left), int(height * top), int(width * right), int(height * bottom))))
        if box.size == 0 or gold_mask(box).mean() < _MIN_GOLD:
            return False
    return True
