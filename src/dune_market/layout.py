"""Where the game's picture sits inside the captured frame.

The game draws a 16:9 picture. On a 16:10 monitor it is centred between black bars (top and bottom), on a
16:9 monitor it fills the frame. Positions of UI elements are therefore given as fractions of this
"content box", not of the whole frame.
"""

import numpy as np
from PIL import Image

_BAR_BRIGHTNESS = 6  # mean grey level (0-255) of a row or column at or below which it counts as a black bar
_STEP = 4  # look at 4x4 pixel blocks; the bars are tens of pixels thick
_last: tuple[Image.Image | None, tuple[int, int, int, int]] = (None, (0, 0, 0, 0))  # one frame is asked about several times


def content_box(frame: Image.Image) -> tuple[int, int, int, int]:
    """(left, top, right, bottom) of the picture without black bars; the whole frame if none are found."""
    global _last
    cached_frame, cached_box = _last
    if cached_frame is frame:
        return cached_box
    box = _find_content_box(frame)
    _last = (frame, box)
    return box


def _find_content_box(frame: Image.Image) -> tuple[int, int, int, int]:
    width, height = frame.size
    whole = (0, 0, width, height)
    # Shrinking in PIL first is several times faster than turning the whole frame into an array.
    sample = np.asarray(frame.reduce(_STEP).convert("L"), dtype=np.float32)
    rows = np.nonzero(sample.mean(axis=1) > _BAR_BRIGHTNESS)[0]
    cols = np.nonzero(sample.mean(axis=0) > _BAR_BRIGHTNESS)[0]
    if rows.size == 0 or cols.size == 0:
        return whole
    top, bottom = int(rows[0]) * _STEP, min(height, (int(rows[-1]) + 1) * _STEP)
    left, right = int(cols[0]) * _STEP, min(width, (int(cols[-1]) + 1) * _STEP)
    if bottom - top < height * 0.5 or right - left < width * 0.5:
        return whole  # implausible: a dark scene, not bars
    # Snap to the frame edge when the "bar" is only a few pixels.
    return (0 if left < 8 else left, 0 if top < 8 else top, width if width - right < 8 else right,
            height if height - bottom < 8 else bottom)


def region(frame: Image.Image, fractions: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    """Pixel box (left, top, right, bottom) for fractions (left, top, right, bottom) of the content box."""
    left, top, right, bottom = content_box(frame)
    width, height = right - left, bottom - top
    f_left, f_top, f_right, f_bottom = fractions
    return (left + int(width * f_left), top + int(height * f_top), left + int(width * f_right), top + int(height * f_bottom))
