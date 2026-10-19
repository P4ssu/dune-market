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
