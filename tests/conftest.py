from pathlib import Path

import pytest
from PIL import Image

from dune_market.ocr import read_words

SCREENSHOTS = Path(__file__).resolve().parent.parent / "screenshots"
_cache: dict[tuple[str, float], list] = {}


@pytest.fixture(scope="session")
def shot_words():
    """OCR a screenshot once per session; skip the test if the file is missing.

    `scale` resizes the image first so tests can check resolution independence.
    """

    def load(name: str, scale: float = 1.0):
        path = SCREENSHOTS / f"{name}.png"
        if not path.exists():
            pytest.skip(f"missing screenshot {path.name}")
        key = (name, scale)
        if key not in _cache:
            image = Image.open(path).convert("RGB")
            if scale != 1.0:
                image = image.resize((round(image.width * scale), round(image.height * scale)))
            _cache[key] = read_words(image)
        return _cache[key]

    return load
