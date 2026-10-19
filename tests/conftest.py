from pathlib import Path

import pytest
from PIL import Image

from dune_market.ocr import read_header, read_words

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


@pytest.fixture(scope="session")
def shot_crop():
    """OCR one rectangle of a screenshot, the way the hover popup re-reads a tooltip header."""

    def load(name: str, box: tuple[int, int, int, int]):
        path = SCREENSHOTS / f"{name}.png"
        if not path.exists():
            pytest.skip(f"missing screenshot {path.name}")
        image = Image.open(path).convert("RGB").crop(box)
        return read_header(read_words, image, (box[0], box[1]))

    return load


@pytest.fixture(scope="session")
def shot_image():
    """A screenshot as a PIL image; skips the test if the file is missing."""

    def load(name: str):
        path = SCREENSHOTS / f"{name}.png"
        if not path.exists():
            pytest.skip(f"missing screenshot {path.name}")
        return Image.open(path).convert("RGB")

    return load


@pytest.fixture(scope="session")
def friend_frame(shot_image):
    """The owner's 16:10 screenshot as a 16:9 monitor shows it: no black bars, scaled to 1920x1080."""

    def load(name: str):
        image = shot_image(name)
        return image.crop((0, 80, image.width, 1520)).resize((1920, 1080))

    return load
