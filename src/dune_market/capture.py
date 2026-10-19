"""Screen capture and cursor position (Windows)."""

import ctypes
from ctypes import wintypes

import mss
from PIL import Image


def grab_frame() -> Image.Image | None:
    """Capture the primary monitor; None if the capture fails."""
    try:
        with mss.MSS() as sct:
            shot = sct.grab(sct.monitors[1])
            return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    except Exception:
        return None


def cursor_position() -> tuple[int, int]:
    point = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
    return point.x, point.y
