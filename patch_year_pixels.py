#!/usr/bin/env python3
"""
Year-in-Pixels (Show-stopper #1) patch for app/routes/dashboard.py
GitHub-contribution-style grid: 5 rows (Mon-Fri), weeks as columns,
severity colours per day's school-wide attendance %.
5 surgical edits, each anchored on an exact unique string + assertion.
ast.parse proves syntax validity before commit.
"""
import ast

PATH = "app/routes/dashboard.py"

with open(PATH, "r") as f:
    src = f.read()

orig = src

# ---------------------------------------------------------------------------
# EDIT 1 - helper build_year_pixels, inserted before index()
# ---------------------------------------------------------------------------
HELPER = '''def build_year_pixels(daily_data):
    """daily_data: list of (date_str 'YYYY-MM-DD', pct). Builds a Mon-Fri x weeks
    grid (GitHub contribution style). Severity colours match dashboard thresholds."""
    if not daily_data:
        return '<div class="big-label" style="opacity:0.6;">No attendance data yet</div>'
    from datetime import datetime
    pct_by_date = {}
    for d, p in daily_data:
        pct_by_date[d] = p
    parsed = []
    for d, p in daily_data:
        try:
            dt = datetime.strptime(d, '%Y-%m-%d')
        except Exception:
            continue
        parsed.append((dt, p))
    if not parsed:
        return '<div class="big-label" style="opacity:0.6;">No attendance data yet</div>'
    parsed.sort(key=lambda x: x[0])
    # ISO week key (year, week) -> column index
    week_keys = []
    for dt, _ in parsed:
        iso = dt.isocalendar()
        key = (iso[0], iso[1])
        if key not in week_keys:
            week_keys.append(key)
    col_of = {k: i for i, k in enumerate(week_keys)}
    n_cols = len(week_keys)

    def cell_class(pct):
        if pct is None:
            return 'yp-none'
        if pct >= 95:
            return 'yp-green'
        if pct >= 90:
            return 'yp-amber'
        return 'yp-red'

    # grid[row 0..4 = Mon..Fri][col] = pct
    grid = [[None] * n_cols for _ in range(5)]
    date_grid = [[None] * n_cols for _ in range(5)]
    for dt, p in parsed:
        wd = dt.weekday()  # Mon=0 .. Sun=6
        if wd > 4:
            continue  # skip weekend captures if any
        iso = dt.isocalendar()
        c = col_of[(iso[0], iso[1])]
        grid[wd][c] = p
        date_grid[wd][c] = dt.strftime('%-d %b')

    day_labels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
    rows = []
    for r in range(5):
        cells = ''
        for c in range(n_cols):
            p = grid[r][c]
            lbl = date_grid[r][c]
            title = f'{lbl}: {p:.0f}%' if (p is not None and lbl) else ''
            cells += f'<div class="yp-cell {cell_class(p)}" title="{title}"></div>'
        rows.append(
            f'<div class="yp-row"><span class="yp-daylabel">{day_labels[r]}</span>'
            f'<div class="yp-cells" style="grid-template-columns:repeat({n_cols},1fr);">{cells}</div></div>'
        )
    return '<div class="year-pixels">' + ''.join(rows) + '</div>'


'''

ANCHOR1 = "@dashboard_bp.route('/')\ndef index():"
assert src.count(ANCHOR1) == 1, "EDIT1 anchor not unique/found"
src = src.replace(ANCHOR1, HELPER + ANCHOR1, 1)

# ---------------------------------------------------------------------------
# EDIT 2 - build year_pixels_html near other *_html builders
# Anchor: sparkline_svg assignment (unique, reuses daily_attendance)
# ---------------------------------------------------------------------------
ANCHOR2 = "    sparkline_svg = build_sparkline(daily_attendance)\n"
assert src.count(ANCHOR2) == 1, "EDIT2 anchor not unique/found"
src = src.replace(ANCHOR2, ANCHOR2 + "    year_pixels_html = build_year_pixels(daily_attendance)\n", 1)

# ---------------------------------------------------------------------------
# EDIT 3 - CSS, inserted after .bar-fill rule (unique)
# ---------------------------------------------------------------------------
ANCHOR3 = "        .bar-fill {{ background: linear-gradient(90deg, #0891b2, #06b6d4, #22d3ee); height: 100%; border-radius: 4px; }}\n"
assert src.count(ANCHOR3) == 1, "EDIT3 anchor not unique/found"

CSS = '''        .year-pixels {{ display: flex; flex-direction: column; gap: 3px; margin-top: 16px; }}
        .yp-row {{ display: grid; grid-template-columns: 32px 1fr; gap: 8px; align-items: center; }}
        .yp-daylabel {{ font-size: 10px; opacity: 0.55; text-align: right; }}
        .yp-cells {{ display: grid; gap: 3px; }}
        .yp-cell {{ aspect-ratio: 1; border-radius: 2px; min-height: 12px; }}
        .yp-green {{ background: #22c55e; }}
        .yp-amber {{ background: #f59e0b; }}
        .yp-red {{ background: #ef4444; }}
        .yp-none {{ background: rgba(255,255,255,0.05); }}
        .yp-legend {{ display: flex; gap: 14px; font-size: 11px; opacity: 0.8; margin-top: 14px; flex-wrap: wrap; justify-content: center; }}
        .yp-leg-item {{ display: flex; align-items: center; gap: 5px; }}
        .yp-swatch {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; }}
'''
src = src.replace(ANCHOR3, ANCHOR3 + CSS, 1)

# ---------------------------------------------------------------------------
# EDIT 4 - card block, inserted at TOP of card stack (before YTD card)
# Anchor: opening of cards div + start of first (YTD) card
# ---------------------------------------------------------------------------
ANCHOR4 = '''        <div class="cards">
            <div class="card">
                <div class="card-header">
                    <span class="card-title">📊 Attendance — Year to Date</span>'''
assert src.count(ANCHOR4) == 1, "EDIT4 anchor not unique/found"

CARD = '''        <div class="cards">
            <div class="card">
                <div class="card-header">
                    <span class="card-title">\U0001F5D3\uFE0F Attendance \u2014 The Year So Far</span>
                    <span class="card-status status-info">{days_counted} days</span>
                </div>
                {year_pixels_html}
                <div class="yp-legend">
                    <span class="yp-leg-item"><span class="yp-swatch yp-green"></span>95%+</span>
                    <span class="yp-leg-item"><span class="yp-swatch yp-amber"></span>90\u201395%</span>
                    <span class="yp-leg-item"><span class="yp-swatch yp-red"></span>&lt;90%</span>
                </div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">📊 Attendance — Year to Date</span>'''
src = src.replace(ANCHOR4, CARD, 1)

# ---------------------------------------------------------------------------
# Verify + write
# ---------------------------------------------------------------------------
assert src != orig, "No changes applied!"
ast.parse(src)

with open(PATH, "w") as f:
    f.write(src)

print("OK: 4 edits applied, ast.parse passed.")
print("  - build_year_pixels helper added")
print("  - year_pixels_html builder added")
print("  - year-pixels CSS added")
print("  - Year-in-Pixels card inserted at top of stack")
