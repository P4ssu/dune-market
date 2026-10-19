"""Screen capture and cursor position (Windows)."""

import ctypes
import threading
from ctypes import wintypes

import mss
from PIL import Image


_local = threading.local()


def grab_frame() -> Image.Image | None:
    """Capture the primary monitor; None if the capture fails."""
    try:
        sct = getattr(_local, "sct", None)
        if sct is None:
            sct = _local.sct = mss.MSS()  # one per thread, reused: creating it each time costs ~20 ms
        shot = sct.grab(sct.monitors[1])
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    except Exception:
        _local.sct = None
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
