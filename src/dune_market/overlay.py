"""The popup and notice windows, and the background loops that drive them.

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
from PyQt6.QtCore import QObject, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QApplication, QLabel

from dune_market.banner import find_banner
from dune_market.capture import cursor_position, game_is_active, grab_frame
from dune_market.popup import (
    HoverTracker,
    PopupData,
    hover_popup,
    render_html,
    render_toast_html,
    scan_toast_lines,
)
from dune_market.scanner import Scanner
from dune_market.screens import exchange_tab_open
from dune_market.store import PriceStore

log = logging.getLogger(__name__)

_EXCHANGE_CHECK_TTL_S = 3.0  # the Exchange tab bar rarely changes, so a hover reuses the last answer


class PopupWindow(QLabel):
    """Frameless, always-on-top panel with a painted dark background and gold border.

    The background is painted here (a stylesheet background is not drawn on a transparent window).
    Default: transparent corners and click-through. `solid=True` uses a plain opaque window instead,
    which some games' display modes show when they hide transparent ("layered") windows.
    """

    def __init__(self, solid: bool = False):
        super().__init__()
        self._solid = solid
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
        if not solid:
            flags |= Qt.WindowType.WindowTransparentForInput
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        if not solid:
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setFont(QFont("Segoe UI", 10))
        self.setContentsMargins(18, 12, 16, 12)
        self.setMinimumWidth(300)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.75, 0.75, -0.75, -0.75)
        path = QPainterPath()
        path.addRoundedRect(rect, 0 if self._solid else 10, 0 if self._solid else 10)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor(38, 31, 22, 246))
        gradient.setColorAt(1, QColor(21, 17, 12, 246))
        painter.fillPath(path, gradient)
        painter.setPen(QPen(QColor(150, 124, 70), 1.5))
        painter.drawPath(path)
        painter.fillRect(QRectF(0, 12, 3, self.height() - 24), QColor(214, 178, 96))
        painter.end()
        super().paintEvent(event)

    def _place(self, left: int, top: int) -> None:
        """Move to (left, top) in Qt (logical) pixels, kept on screen, and show without taking focus."""
        screen = QGuiApplication.primaryScreen()
        if screen:
            area = screen.geometry()
            left = max(area.x(), min(left, area.x() + area.width() - self.width()))
            top = max(area.y(), min(top, area.y() + area.height() - self.height()))
        self.move(left, top)
        self.show()
        self._raise_to_top()

    @staticmethod
    def _ratio() -> float:
        screen = QGuiApplication.primaryScreen()
        return screen.devicePixelRatio() if screen else 1.0

    def show_html(self, html: str, x: int, y: int, centered: bool = False) -> None:
        """Show rich text at frame pixel (x, y), or horizontally centred on the screen."""
        self.setText(html)
        self.adjustSize()
        left, top = int(x / self._ratio()), int(y / self._ratio())  # frame pixels are physical
        screen = QGuiApplication.primaryScreen()
        if centered and screen:
            left = screen.geometry().x() + (screen.geometry().width() - self.width()) // 2
        self._place(left, top)

    def show_popup(self, popup: PopupData) -> None:
        """Show above the tooltip banner (never over its text); beside it if there is no room above."""
        self.setText(render_html(popup.lines))
        self.adjustSize()
        ratio = self._ratio()
        if popup.anchor is None:
            self._place(int(popup.x / ratio), int(popup.y / ratio))
            return
        ax, ay, aw, ah = (int(v / ratio) for v in popup.anchor)
        gap = 10
        left, top = ax, ay - self.height() - gap
        if top < 0:
            left, top = ax + aw + gap, ay
            screen = QGuiApplication.primaryScreen()
            if screen and left + self.width() > screen.geometry().width():
                left = ax - self.width() - gap
        self._place(left, top)

    def hide_popup(self) -> None:
        self.hide()

    def _raise_to_top(self) -> None:
        """Re-assert "topmost" without taking focus, so a borderless game window does not cover the window."""
        try:
            # HWND_TOPMOST = -1; flags: SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE
            ctypes.windll.user32.SetWindowPos(
                ctypes.c_void_p(int(self.winId())), ctypes.c_void_p(-1), 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0010
            )
        except Exception:
            log.debug("could not raise the window", exc_info=True)


class _Signals(QObject):
    show = pyqtSignal(object)
    hide = pyqtSignal()
    toast = pyqtSignal(object)


def make_lookup(
    store: PriceStore,
    active: Callable[[], bool] = game_is_active,
    grab: Callable[[], Image.Image | None] = grab_frame,
    debug: bool = False,
    exchange_check: Callable[[Image.Image], bool] | None = None,
    clock: Callable[[], float] = time.monotonic,
    lookup_fn: Callable | None = None,
) -> Callable[[tuple[int, int]], PopupData | None]:
    """The lookup the hover loop runs; it does nothing unless the game is in front."""
    check = exchange_check or exchange_tab_open
    remembered: list = [False, float("-inf")]

    def exchange_open(frame: Image.Image) -> bool:
        if clock() - remembered[1] >= _EXCHANGE_CHECK_TTL_S:
            remembered[:] = [check(frame), clock()]
        return remembered[0]

    header_cache: dict = {}

    def default_lookup(frame, cursor, exchange):
        return hover_popup(frame, cursor, store, datetime.now(timezone.utc), exchange_open=exchange, header_cache=header_cache)

    run = lookup_fn or default_lookup

    def lookup(cursor: tuple[int, int]) -> PopupData | None:
        if not active():
            return None
        started = time.monotonic()
        frame = grab()
        grabbed = time.monotonic()
        popup = run(frame, cursor, exchange_open)
        if debug:
            size = frame.size if frame else None
            log.info("lookup at %s on frame %s: grab %.2fs, rest %.2fs -> %s", cursor, size, grabbed - started,
                     time.monotonic() - grabbed, popup.lines if popup else None)
            if frame is not None and popup is None:
                frame.save("debug-last-frame.png")  # the screen the lookup found nothing on
        return popup

    def still_visible(popup: PopupData, cursor: tuple[int, int]) -> bool:
        """True while the tooltip the popup was built for is still drawn where it was."""
        if not active() or popup.anchor is None:
            return False
        frame = grab()
        banner = find_banner(frame, cursor) if frame is not None else None
        if banner is None:
            return False
        ax, ay, aw, _ = popup.anchor
        return abs(banner.x - ax) <= 6 and abs(banner.y - ay) <= 6 and abs(banner.w - aw) <= 10

    lookup.still_visible = still_visible
    return lookup


def run_overlay(
    store: PriceStore,
    debug: bool = False,
    solid: bool = False,
    contributor: str | None = None,
) -> None:
    """Show the hover popup; with a `contributor` name, also scan the Exchange and show in-game notices."""
    app = QApplication([])
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # let Ctrl+C stop the program
    window = PopupWindow(solid=solid)
    notice = PopupWindow(solid=solid)
    notice.setMinimumWidth(360)
    notice_timer = QTimer()
    notice_timer.setSingleShot(True)
    notice_timer.timeout.connect(notice.hide_popup)

    def show_notice(lines: list[str], seconds: float) -> None:
        screen = QGuiApplication.primaryScreen()
        ratio = screen.devicePixelRatio() if screen else 1.0
        top = int((screen.geometry().height() * 0.07) * ratio) if screen else 80
        notice.show_html(render_toast_html(lines), 0, top, centered=True)
        notice_timer.start(int(seconds * 1000))

    signals = _Signals()
    signals.show.connect(window.show_popup)
    signals.hide.connect(window.hide_popup)
    signals.toast.connect(lambda lines: show_notice(lines, 3.0))
    if debug:
        signals.show.connect(lambda popup: log.info("popup shown at (%s, %s)", popup.x, popup.y))
        signals.hide.connect(lambda: log.info("popup hidden"))

    lookup = make_lookup(store, debug=debug)
    tracker = HoverTracker(
        lookup=lookup,
        on_show=signals.show.emit,
        on_hide=signals.hide.emit,
        current_cursor=cursor_position,
        still_visible=lookup.still_visible,
    )

    def hover_loop() -> None:
        while True:
            try:
                if game_is_active():
                    tracker.tick(cursor_position(), time.monotonic())
            except Exception:
                log.exception("hover loop error")
            time.sleep(0.05)

    threading.Thread(target=hover_loop, daemon=True).start()

    if contributor:
        scanner = Scanner(store, contributor, active=game_is_active)

        def scan_loop() -> None:
            while True:
                try:
                    if scanner.scan_once(datetime.now(timezone.utc)):
                        signals.toast.emit(
                            scan_toast_lines(scanner.last_label, scanner.last_rows, scanner.last_new, scanner.session_total)
                        )
                except Exception:
                    log.exception("scan loop error")
                time.sleep(scanner.idle_delay)

        threading.Thread(target=scan_loop, daemon=True).start()

    what = "scanning and price popups" if contributor else "price popups"
    QTimer.singleShot(1500, lambda: show_notice(["Dune Market", f"Running: {what}", "Hover an item in your inventory."], 4.0))
    print(f"Dune Market running ({what}). Press Ctrl+C to stop.")
    app.exec()
