"""OCR wrapper that returns `Word` spans."""

import os
import re
import threading
from collections.abc import Callable

import numpy as np
from PIL import Image

from dune_market.models import Word

_engine = None
_engine_lock = threading.Lock()  # the scanner and the hover loop share one engine


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        # More threads than this is slower, not faster: ~1.2 s instead of ~5 s per frame on a 24-core CPU.
        # det_limit_type="max": the default ("min") blows small crops up to 736 px on the short side,
        # which made reading a 600x85 tooltip header take 1 s instead of 0.1 s.
        _engine = RapidOCR(
            intra_op_num_threads=min(6, os.cpu_count() or 1),
            inter_op_num_threads=1,
            det_limit_type="max",
            det_limit_side_len=2600,
        )
    return _engine


def read_words(image: Image.Image, offset: tuple[int, int] = (0, 0), scale: float = 1.0) -> list[Word]:
    """OCR an image; positions are shifted by `offset` (for cropped regions).

    `scale` > 1 enlarges the image first (tiny glyphs such as the grade number need it); the
    returned positions are still in the original image's pixels.
    """
    if scale != 1.0:
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    with _engine_lock:
        result, _ = _get_engine()(np.array(image.convert("RGB")))
    words = []
    for box, text, _score in result or []:
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        words.append(
            Word(
                text=text,
                x=min(xs) / scale + offset[0],
                y=min(ys) / scale + offset[1],
                w=(max(xs) - min(xs)) / scale,
                h=(max(ys) - min(ys)) / scale,
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


def name_line_extent(words: list[Word], first: Word) -> tuple[str, float]:
    """The full text of the line starting at `first`, and the x where it ends.

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
    return " ".join(parts), end


def name_line(words: list[Word], first: Word) -> str:
    return name_line_extent(words, first)[0]


def name_key(name: str) -> str:
    """Spelling-independent key: the OCR drops spaces unpredictably ("Robeofthe Sisterhood")."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


_BADGE_RE = re.compile(r"^\d{1,2}$")
_BADGE_REACH = 4  # the badge sits within this many category-line widths of the header's left edge


def find_grade_badge(words: list[Word], cat: Word, line_end: float, line_centre: float) -> str:
    """The grade number shown at the right end of a tooltip/panel header, or "0" when there is none."""
    badges = [
        w for w in words
        if _BADGE_RE.match(w.text.strip())
        and abs(w.y + w.h / 2 - line_centre) < 30
        and line_end <= w.x < cat.x + _BADGE_REACH * cat.w
    ]
    return min(badges, key=lambda w: w.x).text.strip() if badges else "0"


def read_header(
    read: Callable[..., list[Word]], crop: Image.Image, origin: tuple[int, int], badge_fraction: float = 0.3
) -> list[Word]:
    """OCR a tooltip/panel header crop: normal-size text plus the tiny grade digit.

    Enlarging makes the grade digit readable but garbles letter case ("COmPONENTS"), so the text
    comes from the plain read and only digit-only spans are taken from an enlarged read of the
    right end of the header, where the badge sits (a small crop, so it is quick).
    """
    words = read(crop, origin)
    if any(_BADGE_RE.match(w.text.strip()) for w in words):
        return words
    left = int(crop.width * (1 - badge_fraction))
    part = crop.crop((left, 0, crop.width, crop.height))
    return words + [w for w in read(part, (origin[0] + left, origin[1]), scale=2) if _BADGE_RE.match(w.text.strip())]
