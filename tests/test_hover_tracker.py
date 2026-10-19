import os

from PIL import Image

from dune_market.popup import HoverTracker, PopupData


def make(lookup):
    events = []
    tracker = HoverTracker(lookup, on_show=lambda p: events.append(("show", p.lines)),
                           on_hide=lambda: events.append(("hide",)))
    return tracker, events


POPUP = PopupData(["Item", "Avg price: 1"], 10, 10)


def test_lookup_fires_once_after_cursor_is_still():
    calls = []
    tracker, events = make(lambda pos: calls.append(pos) or POPUP)
    for t in (0.0, 0.2, 0.4, 0.6, 0.8):
        tracker.tick((100, 100), t)
    assert calls == [(100, 100)]
    assert events == [("show", ["Item", "Avg price: 1"])]


def test_moving_cursor_hides_popup_and_new_stop_looks_up_again():
    tracker, events = make(lambda pos: POPUP)
    for t in (0.0, 0.5):
        tracker.tick((100, 100), t)
    tracker.tick((300, 300), 0.6)
    for t in (1.1,):
        tracker.tick((300, 300), t)
    assert [e[0] for e in events] == ["show", "hide", "show"]


def test_small_jitter_does_not_hide():
    tracker, events = make(lambda pos: POPUP)
    tracker.tick((100, 100), 0.0)
    tracker.tick((100, 100), 0.5)
    tracker.tick((103, 101), 0.6)
    assert [e[0] for e in events] == ["show"]


def test_no_popup_when_lookup_finds_nothing():
    tracker, events = make(lambda pos: None)
    for t in (0.0, 0.5, 1.0):
        tracker.tick((100, 100), t)
    assert events == []


def test_lookup_error_is_swallowed():
    def broken(pos):
        raise RuntimeError("ocr blew up")

    tracker, events = make(broken)
    for t in (0.0, 0.5, 1.0):
        tracker.tick((100, 100), t)
    assert events == []


def test_overlay_window_shows_and_hides_offscreen():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt6.QtWidgets import QApplication

    from dune_market.overlay import PopupWindow

    app = QApplication.instance() or QApplication([])
    window = PopupWindow()
    window.show_popup(POPUP)
    assert window.isVisible() and "Item" in window.text()
    window.hide_popup()
    assert not window.isVisible()
    app.processEvents()


def test_lookup_does_nothing_while_the_game_is_not_in_front():
    from dune_market.overlay import make_lookup

    grabbed = []
    lookup = make_lookup(store=None, active=lambda: False, grab=lambda: grabbed.append(1))
    assert lookup((100, 100)) is None
    assert grabbed == []


def test_solid_window_is_opaque_and_not_translucent():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import QApplication

    from dune_market.overlay import PopupWindow

    app = QApplication.instance() or QApplication([])
    solid, normal = PopupWindow(solid=True), PopupWindow()
    assert not solid.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert normal.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert not (solid.windowFlags() & Qt.WindowType.WindowTransparentForInput)
    assert normal.windowFlags() & Qt.WindowType.WindowTransparentForInput
    solid.show_popup(POPUP)
    assert solid.isVisible()
    app.processEvents()


def test_exchange_check_is_remembered_for_a_moment():
    from dune_market.overlay import make_lookup

    checks, now = [], [0.0]
    lookup = make_lookup(store=None, active=lambda: True, grab=lambda: None, exchange_check=lambda frame: checks.append(1) or False,
                         clock=lambda: now[0], lookup_fn=lambda frame, cursor, check: check(frame) and None)
    lookup((1, 1)); now[0] = 0.5; lookup((1, 1))
    assert checks == [1]  # second lookup within the remembered window
    now[0] = 3.0; lookup((1, 1))
    assert checks == [1, 1]


def test_popup_paints_its_own_dark_background_in_both_modes():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt6.QtWidgets import QApplication

    from dune_market.overlay import PopupWindow

    app = QApplication.instance() or QApplication([])
    for solid in (False, True):
        window = PopupWindow(solid=solid)
        window.show_popup(POPUP)
        app.processEvents()
        image = window.grab().toImage()
        pixel = image.pixelColor(image.width() // 2, image.height() - 6)  # empty space near the bottom edge
        assert pixel.alpha() > 200 and pixel.lightness() < 70, (solid, pixel.name(), pixel.alpha())


# --- popup stays while the same tooltip is under the cursor -----------------------------------


def test_popup_stays_while_the_tooltip_is_still_there_after_a_small_move():
    events = []
    tracker = HoverTracker(lambda pos: POPUP, on_show=lambda p: events.append("show"), on_hide=lambda: events.append("hide"),
                           still_visible=lambda popup, cursor: True)
    tracker.tick((100, 100), 0.0)
    tracker.tick((100, 100), 0.5)
    tracker.tick((140, 120), 0.6)  # moved a bit, same item
    tracker.tick((160, 130), 0.7)
    assert events == ["show"]


def test_popup_hides_when_the_tooltip_is_gone():
    events = []
    gone = {"now": False}
    tracker = HoverTracker(lambda pos: POPUP, on_show=lambda p: events.append("show"), on_hide=lambda: events.append("hide"),
                           still_visible=lambda popup, cursor: not gone["now"])
    tracker.tick((100, 100), 0.0)
    tracker.tick((100, 100), 0.5)
    gone["now"] = True
    tracker.tick((400, 300), 0.6)
    assert events == ["show", "hide"]


def test_lookup_retries_until_the_tooltip_appears():
    answers = iter([None, None, POPUP])
    events = []
    tracker = HoverTracker(lambda pos: next(answers), on_show=lambda p: events.append("show"), on_hide=lambda: events.append("hide"))
    for t in (0.0, 0.15, 0.3, 0.45, 0.6, 0.75):
        tracker.tick((100, 100), t)
    assert events == ["show"]


def test_lookup_gives_up_after_a_while_and_waits_for_the_cursor_to_move():
    calls = []
    tracker = HoverTracker(lambda pos: calls.append(1) or None, on_show=lambda p: None, on_hide=lambda: None)
    for i in range(80):
        tracker.tick((100, 100), i * 0.1)  # 8 seconds without a tooltip
    assert 3 <= len(calls) <= 20


def test_still_visible_compares_the_banner_with_the_one_the_popup_was_built_for(shot_image):
    from dune_market.banner import find_banner
    from dune_market.overlay import make_lookup

    image = shot_image("item hover")
    banner = find_banner(image, (842, 927))
    popup = PopupData(["x"], banner.x, banner.y - 100, anchor=(banner.x, banner.y, banner.w, banner.h))
    lookup = make_lookup(store=None, active=lambda: True, grab=lambda: image)
    assert lookup.still_visible(popup, (860, 940)) is True  # moved a little, banner is where it was
    moved = PopupData(["x"], 0, 0, anchor=(banner.x + 200, banner.y, banner.w, banner.h))
    assert lookup.still_visible(moved, (860, 940)) is False  # a different tooltip position
    assert make_lookup(store=None, active=lambda: True, grab=lambda: Image.new("RGB", (2560, 1600))).still_visible(popup, (860, 940)) is False


def test_popup_is_placed_above_the_tooltip_banner_or_beside_it():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PyQt6.QtWidgets import QApplication

    from dune_market.overlay import PopupWindow

    app = QApplication.instance() or QApplication([])
    window = PopupWindow()
    # the offscreen test screen is 800x600
    window.show_popup(PopupData(["Item", "Avg price: 1"], 100, 300, anchor=(100, 400, 300, 72)))
    assert window.geometry().bottom() < 400  # above the banner
    window.show_popup(PopupData(["Item", "Avg price: 1"], 50, 10, anchor=(50, 20, 300, 72)))
    assert window.geometry().left() >= 360  # no room above: beside the banner, to its right
    app.processEvents()
