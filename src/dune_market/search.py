"""What the search window shows (pure text rendering; the window itself is in overlay.py)."""

from datetime import datetime

from dune_market.models import ItemStats
from dune_market.popup import AMBER, GOLD, GREEN, MUTED, RED, TEXT, _age, _esc

SEARCH_HINT = "Type an item name"


def _row(s: ItemStats, now: datetime) -> str:
    grade = "unknown" if s.key.grade == "unknown" else s.key.grade
    avg = "n/a" if s.avg is None else f"{s.avg:,}"
    if s.avg is not None and s.trend_pct:
        arrow, color = ("▲", GREEN) if s.trend_pct > 0 else ("▼", RED)
        avg += f' <span style="color:{color}">{arrow}{abs(s.trend_pct):g}%</span>'
    cheapest = "n/a" if s.cheapest is None else f"{s.cheapest:,}"
    age_color = AMBER if s.stale else MUTED
    old = " (old)" if s.stale else ""
    return (
        "<tr>"
        f'<td style="color:{TEXT};font-weight:600">{_esc(s.key.name)}'
        f'<br><span style="color:{MUTED};font-size:8pt">{_esc(s.key.category)}</span></td>'
        f'<td align="center" style="color:{GOLD}">{_esc(grade)}</td>'
        f'<td align="right" style="color:{TEXT}">{avg}</td>'
        f'<td align="right" style="color:{GOLD};font-weight:600">{cheapest}</td>'
        f'<td style="color:{age_color};font-size:8pt">&nbsp;&nbsp;{_age(s.updated_at, now)} · {_esc(s.contributor)}{old}</td>'
        "</tr>"
    )


def render_search_html(query: str, results: list[ItemStats], now: datetime) -> str:
    """Rich text for the results area under the search box."""
    if not query.strip():
        return f'<div style="color:{MUTED}">{SEARCH_HINT}</div>'
    if not results:
        return f'<div style="color:{MUTED}">No items found for “{_esc(query.strip())}”.</div>'
    head = "".join(
        f'<td align="{align}" style="color:{MUTED};font-size:8pt">{label}</td>'
        for label, align in (("ITEM", "left"), ("GRADE", "center"), ("AVG", "right"), ("CHEAPEST", "right"), ("UPDATED", "left"))
    )
    return (
        '<table width="100%" cellspacing="0" cellpadding="4">'
        f"<tr>{head}</tr>{''.join(_row(s, now) for s in results)}</table>"
    )
