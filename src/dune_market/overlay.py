"""The popup window and the background hover loop.

The overlay only appears over the game when it runs in borderless windowed
mode; exclusive fullscreen hides every other window.
"""

import threading
import time
from datetime import datetime, timezone

from PyQt6.QtCore import QObject, Qt, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QLabel

from dune_market.capture import cursor_position, grab_frame
from dune_market.popup import HoverTracker, PopupData, hover_popup
from dune_market.store import PriceStore


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

    def hide_popup(self) -> None:
        self.hide()


class _Signals(QObject):
    show = pyqtSignal(object)
    hide = pyqtSignal()


def run_overlay(store: PriceStore) -> None:
    app = QApplication([])
    window = PopupWindow()
    signals = _Signals()
    signals.show.connect(window.show_popup)
    signals.hide.connect(window.hide_popup)

    tracker = HoverTracker(
        lookup=lambda cursor: hover_popup(grab_frame(), cursor, store, datetime.now(timezone.utc)),
        on_show=signals.show.emit,
        on_hide=signals.hide.emit,
    )

    def loop() -> None:
        while True:
            tracker.tick(cursor_position(), time.monotonic())
            time.sleep(0.1)

    threading.Thread(target=loop, daemon=True).start()
    print("Overlay running. Hover an item in your inventory. Press Ctrl+C to stop.")
    app.exec()
