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


def foreground_window_title() -> str:
    """Title of the window in front, "" if there is none."""
    user32 = ctypes.windll.user32
    handle = user32.GetForegroundWindow()
    buffer = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(handle, buffer, 256)
    return buffer.value


def game_is_active() -> bool:
    """True while Dune: Awakening is the window in front (read-only; no input to the game)."""
    return "dune: awakening" in foreground_window_title().lower()
