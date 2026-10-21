from dune_market.popup import GOLD, GREEN, MUTED, RED, AMBER, render_html, scan_toast_lines

FULL = [
    "Maula Pistol Blueprint", "Grade: 1", "Lowest: 9,800 ▲ 8%", "Average: 12,400", "Listings: 14",
    "Updated 2 h ago by Mari",
]


def test_html_has_title_rows_and_green_up_arrow():
    html = render_html(FULL)
    assert "Maula Pistol Blueprint" in html and GOLD in html
    assert "Lowest" in html and "9,800" in html and "Average" in html and "12,400" in html
    assert f'color:{GREEN}' in html and "▲" in html and "8%" in html
    assert "GRADE 1" in html
    assert "Updated 2 h ago by Mari" in html


def test_html_down_arrow_is_red():
    html = render_html(["X", "Grade unknown", "Lowest: 100 ▼ 3%"])
    assert f'color:{RED}' in html and "▼" in html and "GRADE UNKNOWN" in html


def test_html_marks_old_data_in_amber():
    html = render_html(["X", "Grade unknown", "Updated 1 d ago by Mari (old)"])
    assert f'color:{AMBER}' in html


def test_html_no_data_message_is_muted():
    html = render_html(["Unknown Thing", "No price data yet"])
    assert "No price data yet" in html and f'color:{MUTED}' in html


def test_html_escapes_ocr_text():
    html = render_html(["<b>Evil</b> & Co", "No price data yet"])
    assert "<b>Evil" not in html and "&lt;b&gt;Evil" in html and "&amp;" in html


def test_html_one_block_per_grade_with_divider():
    html = render_html(["X", "Grade: 3", "Lowest: 5", "Grade unknown", "Lowest: 4"])
    assert html.count("GRADE") == 2


def test_scan_toast_lines():
    assert scan_toast_lines("Buy tab · GARMENTS - LIGHTARMOR · grade 3", 5, 2, 41) == [
        "Dune Market · scanning",
        "Buy tab · GARMENTS - LIGHTARMOR · grade 3",
        "5 rows read · 2 new items · 41 items this session",
    ]
