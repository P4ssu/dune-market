"""OCR wrapper that returns `Word` spans."""

import re

import numpy as np
from PIL import Image

from dune_market.models import Word

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
    return _engine


def read_words(image: Image.Image, offset: tuple[int, int] = (0, 0)) -> list[Word]:
    """OCR an image; positions are shifted by `offset` (for cropped regions)."""
    result, _ = _get_engine()(np.array(image.convert("RGB")))
    words = []
    for box, text, _score in result or []:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        words.append(
            Word(
                text=text,
                x=min(xs) + offset[0],
                y=min(ys) + offset[1],
                w=max(xs) - min(xs),
                h=max(ys) - min(ys),
            )
        )
    return words


_PRICE_RE = re.compile(r"^\s*(\d{1,3}(?:,\d{3})+|\d+)\s*(\S{0,2})\s*$")


def parse_price(text: str) -> int | None:
    """Parse "56,359", "56,359 S" or "56,359@" (Solari icon read as a symbol).

    Up to two trailing characters are the icon; the grouping regex stops at the
    last full thousands group, so "46,0005" (icon read as a digit) gives 46000.
    """
    match = _PRICE_RE.match(text)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))


_CATEGORY_RE = re.compile(r"^[A-Z&]+(?:-[A-Z&]+)+$")


def normalize_category(text: str) -> str | None:
    """Return "MISC - COMPONENTS" for a category line, or None for other text.

    The OCR drops spaces unpredictably, so all spaces are removed and the hyphen
    is re-spaced. Item names fail the all-uppercase check.
    """
    compact = "".join(text.split())
    if compact != compact.upper() or not _CATEGORY_RE.match(compact):
        return None
    return " - ".join(compact.split("-"))


def normalize_name(text: str) -> str:
    """Re-insert spaces the OCR dropped between joined words."""
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text.strip())
    text = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", text)
    return " ".join(text.split())


_NAME_GAP = 60  # px; a wider gap on the same line starts a different column
_NAME_LINE_TOLERANCE = 12  # px between line centres that still counts as one line


def name_line(words: list[Word], first: Word) -> str:
    """The full text of the line starting at `first`.

    The OCR engine sometimes splits a name into two spans ("Spice-infused
    Plastanium" + "Dust"); spans close to the end of the line belong to it.
    """
    centre = first.y + first.h / 2
    same_line = sorted(
        (
            w for w in words
            if w is not first and w.x > first.x
            and abs(w.y + w.h / 2 - centre) < _NAME_LINE_TOLERANCE
            and parse_price(w.text) is None
        ),
        key=lambda w: w.x,
    )
    parts, end = [first.text], first.x + first.w
    for w in same_line:
        if w.x - end >= _NAME_GAP:
            break
        parts.append(w.text)
        end = w.x + w.w
    return " ".join(parts)
