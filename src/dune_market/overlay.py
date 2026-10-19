"""The popup window and the background hover loop.

The overlay only appears over the game when it runs in borderless windowed
mode; exclusive fullscreen hides every other window.
"""

import ctypes
import logging
import signal
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone

from PIL import Image

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QLabel

from dune_market.capture import cursor_position, game_is_active, grab_frame
from dune_market.popup import HoverTracker, PopupData, hover_popup
from dune_market.store import PriceStore


log = logging.getLogger(__name__)


class PopupWindow(QLabel):
    """Frameless, transparent, click-through, always-on-top price popup."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(
            "background-color: rgba(27, 23, 18, 230); color: #e8d9b5;"
            "padding: 10px; border-radius: 6px; font-size: 15px;"
        )

    def show_popup(self, popup: PopupData) -> None:
        title, *rest = popup.lines
        self.setText("<b>" + title + "</b><br>" + "<br>".join(rest))
        self.adjustSize()
        # Frame pixels are physical; Qt positions are device independent.
        ratio = QGuiApplication.primaryScreen().devicePixelRatio() if QGuiApplication.primaryScreen() else 1.0
        self.move(int(popup.x / ratio), int(popup.y / ratio))
        self.show()
        self._raise_to_top()

    def _raise_to_top(self) -> None:
        """Re-assert "topmost" without taking focus, so a borderless game window does not cover the popup."""
        try:
            # HWND_TOPMOST = -1; flags: SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
            ctypes.windll.user32.SetWindowPos(ctypes.c_void_p(int(self.winId())), ctypes.c_void_p(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010)
        except Exception:
            log.debug("could not raise the popup", exc_info=True)

    def hide_popup(self) -> None:
        self.hide()


class _Signals(QObject):
    show = pyqtSignal(object)
    hide = pyqtSignal()


def make_lookup(
    store: PriceStore,
    active: Callable[[], bool] = game_is_active,
    grab: Callable[[], Image.Image | None] = grab_frame,
    debug: bool = False,
) -> Callable[[tuple[int, int]], PopupData | None]:
    """The lookup the hover loop runs; it does nothing unless the game is in front."""

    def lookup(cursor: tuple[int, int]) -> PopupData | None:
        if not active():
            return None
        started = time.monotonic()
        frame = grab()
        popup = hover_popup(frame, cursor, store, datetime.now(timezone.utc))
        if debug:
            size = frame.size if frame else None
            log.info("lookup at %s on frame %s took %.1fs -> %s", cursor, size, time.monotonic() - started,
                     popup.lines if popup else None)
            if frame is not None and popup is None:
                frame.save("debug-last-frame.png")  # the screen the lookup found nothing on
        return popup

    return lookup


def run_overlay(store: PriceStore, debug: bool = False) -> None:
    app = QApplication([])
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # let Ctrl+C stop the overlay
    window = PopupWindow()
    signals = _Signals()
    signals.show.connect(window.show_popup)
    signals.hide.connect(window.hide_popup)

    tracker = HoverTracker(
        lookup=make_lookup(store, debug=debug),
        on_show=signals.show.emit,
        on_hide=signals.hide.emit,
        current_cursor=cursor_position,
    )

    def loop() -> None:
        while True:
            try:
                if game_is_active():
                    tracker.tick(cursor_position(), time.monotonic())
            except Exception:
                log.exception("hover loop error")
            time.sleep(0.1)

    # A test box a few seconds after start: if it shows over the game, the window itself works.
    test = PopupData(["Dune Market overlay is running", "Hover an item in your inventory."], 100, 100)
    QTimer.singleShot(4000, lambda: window.show_popup(test))
    QTimer.singleShot(12000, window.hide_popup)

    threading.Thread(target=loop, daemon=True).start()
    print("Overlay running. A test box appears at the top left in 4 seconds. Press Ctrl+C to stop.")
    app.exec()
