from PIL import Image

from dune_market.banner import find_banner


def test_finds_the_tooltip_banner_in_each_hover_screenshot(shot_image):
    # (screenshot, cursor, expected banner left/top read off the gold border lines)
    for name, cursor, (x, y) in [
        ("item hover", (842, 927), (982, 851)),
        ("schematic hover", (531, 620), (673, 338)),
        ("blueprint hover", (223, 620), (363, 231)),
    ]:
        banner = find_banner(shot_image(name), cursor)
        assert banner is not None, name
        assert abs(banner.x - x) <= 4 and abs(banner.y - y) <= 4, (name, banner)
        assert 580 <= banner.w <= 620 and 65 <= banner.h <= 80, (name, banner)


def test_no_banner_without_a_tooltip():
    assert find_banner(Image.new("RGB", (2560, 1600)), (800, 800)) is None


def test_banner_far_from_the_cursor_is_ignored(shot_image):
    assert find_banner(shot_image("item hover"), (200, 200)) is None


def test_banner_found_at_other_resolutions(shot_image):
    image = shot_image("schematic hover")
    small = image.resize((1920, 1200))
    banner = find_banner(small, (398, 465))
    assert banner is not None
    assert abs(banner.x - 673 * 0.75) <= 6 and abs(banner.w - 601 * 0.75) <= 10
