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


_PRICE_RE = re.compile(r"^\s*(\d[\d,]*)(?:\s+\S{1,2})?\s*$")


def parse_price(text: str) -> int | None:
    """Parse "56,359" or "56,359 S" (Solari icon read as a symbol) into an int."""
    match = _PRICE_RE.match(text)
    if not match:
        return None
    return int(match.group(1).replace(",", ""))
