from PIL import Image

from dune_market.capture import cursor_position, grab_frame


def test_grab_frame_returns_image_or_none():
    frame = grab_frame()
    assert frame is None or isinstance(frame, Image.Image)


def test_cursor_position_is_a_pair_of_ints():
    x, y = cursor_position()
    assert isinstance(x, int) and isinstance(y, int)
