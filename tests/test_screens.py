from dune_market.models import Screen
from dune_market.screens import classify


def test_classify_sell(shot_words):
    assert classify(shot_words("sell")) == Screen.SELL


def test_classify_buy(shot_words):
    assert classify(shot_words("buy tab")) == Screen.BUY


def test_classify_my_orders(shot_words):
    assert classify(shot_words("my orders tab")) == Screen.MY_ORDERS


def test_classify_inventory_is_other(shot_words):
    assert classify(shot_words("item hover")) == Screen.OTHER


def test_classify_empty_words_is_other():
    assert classify([]) == Screen.OTHER


def test_exchange_bar_detected_by_pixels_on_all_three_tabs(shot_image):
    from dune_market.screens import exchange_tab_open

    for name in ("sell", "buy tab", "my orders tab"):
        assert exchange_tab_open(shot_image(name)) is True, name


def test_exchange_bar_not_detected_elsewhere(shot_image):
    from PIL import Image

    from dune_market.screens import exchange_tab_open

    for name in ("item hover", "schematic hover", "blueprint hover"):
        assert exchange_tab_open(shot_image(name)) is False, name
    assert exchange_tab_open(Image.new("RGB", (2560, 1600))) is False


def test_exchange_bar_detected_at_other_resolutions(shot_image):
    from dune_market.screens import exchange_tab_open

    assert exchange_tab_open(shot_image("sell").resize((1920, 1200))) is True
    assert exchange_tab_open(shot_image("item hover").resize((1920, 1200))) is False


def test_chest_screen_is_not_the_exchange(shot_image):
    """The chest/storage screen has the same Q/E tab bar, with the key boxes a little further left."""
    from dune_market.screens import exchange_tab_open

    for name in ("chest look 1", "chest look 2", "chest look 3", "chest look 4"):
        assert exchange_tab_open(shot_image(name)) is False, name
        assert exchange_tab_open(shot_image(name).resize((1920, 1200))) is False, name
