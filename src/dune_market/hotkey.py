"""A global hotkey (Windows RegisterHotKey): the standard, documented way to be told about one key combination.

It does not read the keyboard in general and does not touch the game; Windows simply tells us when
exactly this combination is pressed.
"""

import ctypes
import logging
import threading
from collections.abc import Callable
from ctypes import wintypes

log = logging.getLogger(__name__)

_MODIFIERS = {"alt": 0x1, "ctrl": 0x2, "control": 0x2, "shift": 0x4, "win": 0x8}
_NAMED_KEYS = {
    "space": 0x20, "enter": 0x0D, "tab": 0x09, "insert": 0x2D, "delete": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "`": 0xC0, "backtick": 0xC0,
}
_MOD_NOREPEAT = 0x4000
_WM_HOTKEY, _WM_QUIT = 0x0312, 0x0012


def _key_code(name: str) -> int | None:
    if len(name) == 1 and name.isalnum() and name.isascii():
        return ord(name.upper())
    if name.startswith("f") and name[1:].isdigit() and 1 <= int(name[1:]) <= 24:
        return 0x70 + int(name[1:]) - 1
    return _NAMED_KEYS.get(name)


def parse_hotkey(text: str) -> tuple[int, int]:
    """"ctrl+shift+f" -> (Windows modifier flags, virtual key code). Raises ValueError for nonsense."""
    parts = [p.strip().lower() for p in text.split("+") if p.strip()]
    modifiers, keys = 0, []
    for part in parts:
        if part in _MODIFIERS:
            modifiers |= _MODIFIERS[part]
        else:
            keys.append(part)
    if len(keys) != 1 or (code := _key_code(keys[0])) is None:
        raise ValueError(
            f"hotkey {text!r} is not valid: use modifiers (ctrl, shift, alt, win) plus exactly one key, "
            "for example ctrl+shift+f or F8"
        )
    return modifiers, code


class HotkeyListener:
    """Calls `on_press` (from a background thread) whenever the hotkey is pressed."""

    def __init__(self, text: str, on_press: Callable[[], None]):
        self._modifiers, self._code = parse_hotkey(text)
        self._on_press = on_press
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="hotkey")
        self._thread_id = 0
        self.registered = False

    def start(self) -> None:
        self._thread.start()

    def wait_ready(self, timeout: float) -> bool:
        return self._ready.wait(timeout)

    def stop(self) -> None:
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, _WM_QUIT, 0, 0)
        self._thread.join(timeout=2)

    def _loop(self) -> None:
        user32 = ctypes.windll.user32
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        self.registered = bool(user32.RegisterHotKey(None, 1, self._modifiers | _MOD_NOREPEAT, self._code))
        self._ready.set()
        if not self.registered:
            log.warning("could not register the search hotkey (another program may use it)")
            return
        message = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                if message.message == _WM_HOTKEY:
                    try:
                        self._on_press()
                    except Exception:
                        log.exception("hotkey handler failed")
        finally:
            user32.UnregisterHotKey(None, 1)
