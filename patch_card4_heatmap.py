#!/usr/bin/env python3
"""
Card 4 - Class Heatmap patch for app/routes/dashboard.py
4 surgical edits, each anchored on an exact unique string + assertion.
ast.parse at the end proves syntax validity before commit.
"""
import ast

PATH = "app/routes/dashboard.py"

with open(PATH, "r") as f:
    src = f.read()

orig = src

# ---------------------------------------------------------------------------
# EDIT 1 - new helper function build_class_heatmap, inserted before index()
# Anchor: the @dashboard_bp.route('/') decorator line for index()
# ---------------------------------------------------------------------------
HELPER = '''def build_class_heatmap(matrix, dates):
    """matrix: list of dicts {code, avg_pct, cells:[(date_str, pct_or_None)...]}
    Rows already sorted best->worst (worst at bottom). Builds HTML grid."""
    if not matrix:
        return '<div class="big-label" style="opacity:0.6;">No attendance data yet</div>'

    def cell_class(pct):
        if pct is None:
            return 'hc-none'
        if pct >= 97:
            return 'hc-dgreen'
        if pct >= 95:
            return 'hc-green'
        if pct >= 90:
            return 'hc-amber'
        return 'hc-red'

    rows = []
    for r in matrix:
        cells = ''.join(
            f'<div class="hm-cell {cell_class(p)}" title="{d}: {("%.0f%%" % p) if p is not None else "no data"}"></div>'
            for (d, p) in r['cells']
        )
        avg = r['avg_pct']
        rows.append(
            f'<div class="hm-row">'
            f'<span class="hm-code">{r["code"]}</span>'
            f'<div class="hm-cells">{cells}</div>'
            f'<span class="hm-avg">{avg:.0f}%</span>'
            f'</div>'
        )
    return '<div class="heatmap">' + ''.join(rows) + '</div>'


'''

ANCHOR1 = "@dashboard_bp.route('/')\ndef index():"
assert src.count(ANCHOR1) == 1, "EDIT1 anchor not unique/found"
src = src.replace(ANCHOR1, HELPER + ANCHOR1, 1)

# ---------------------------------------------------------------------------
# EDIT 2 - heatmap query block, inserted right after chronic_all is built
# Anchor: the closing of the chronic query + assignment, unique tail string
# ---------------------------------------------------------------------------
ANCHOR2 = "        chronic_all = [dict(r) for r in cursor.fetchall()]\n"
assert src.count(ANCHOR2) == 1, "EDIT2 anchor not unique/found"

QUERY = '''
        # --- Card 4: class heatmap (25 classes x last 14 captured days) ---
        cursor.execute(\'\'\'
            SELECT DISTINCT date FROM attendance
            WHERE tenant_id = ?
            ORDER BY date DESC LIMIT 14
        \'\'\', (TENANT_ID,))
        hm_dates = sorted([r['date'] for r in cursor.fetchall()])

        hm_matrix = []
        if hm_dates:
            placeholders = ','.join('?' for _ in hm_dates)
            cursor.execute(f\'\'\'
                SELECT mg.group_name AS code, a.date AS d,
                  SUM(CASE WHEN ae.status='Present' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS pct
                FROM mentor_group mg
                JOIN learner l ON l.mentor_group_id = mg.id AND COALESCE(l.is_active,1)=1
                JOIN attendance_entry ae ON ae.learner_id = l.id
                JOIN attendance a ON a.id = ae.attendance_id AND a.date IN ({placeholders})
                WHERE mg.tenant_id = ?
                GROUP BY mg.group_name, a.date
            \'\'\', (*hm_dates, TENANT_ID))
            by_class = {}
            for r in cursor.fetchall():
                by_class.setdefault(r['code'], {})[r['d']] = r['pct']
            cursor.execute('SELECT group_name FROM mentor_group WHERE tenant_id = ? ORDER BY group_name', (TENANT_ID,))
            all_codes = [r['group_name'] for r in cursor.fetchall()]
            for code in all_codes:
                day_map = by_class.get(code, {})
                cells = [(d, day_map.get(d)) for d in hm_dates]
                vals = [p for (_, p) in cells if p is not None]
                avg = sum(vals) / len(vals) if vals else 0
                hm_matrix.append({'code': code, 'avg_pct': avg, 'cells': cells})
            # best on top, worst at bottom
            hm_matrix.sort(key=lambda x: x['avg_pct'], reverse=True)
'''
src = src.replace(ANCHOR2, ANCHOR2 + QUERY, 1)

# ---------------------------------------------------------------------------
# EDIT 3 - build heatmap HTML + date labels, near other *_html assignments
# Anchor: grade_bars_html assignment line (unique)
# ---------------------------------------------------------------------------
ANCHOR3 = "    grade_bars_html = build_grade_bars(grade_data)\n"
assert src.count(ANCHOR3) == 1, "EDIT3 anchor not unique/found"

BUILD = '''    heatmap_html = build_class_heatmap(hm_matrix, hm_dates)
    if hm_dates:
        hm_first_lbl = format_date_short(hm_dates[0])
        hm_last_lbl = format_date_short(hm_dates[-1])
    else:
        hm_first_lbl = hm_last_lbl = ''
'''
src = src.replace(ANCHOR3, ANCHOR3 + BUILD, 1)

# ---------------------------------------------------------------------------
# EDIT 4a - CSS for heatmap, inserted after .bar-fill rule (unique)
# ---------------------------------------------------------------------------
ANCHOR4 = "        .bar-fill {{ background: linear-gradient(90deg, #0891b2, #06b6d4, #22d3ee); height: 100%; border-radius: 4px; }}\n"
assert src.count(ANCHOR4) == 1, "EDIT4a anchor not unique/found"

CSS = '''        .heatmap {{ display: flex; flex-direction: column; gap: 3px; margin-top: 16px; }}
        .hm-row {{ display: grid; grid-template-columns: 48px 1fr 38px; gap: 8px; align-items: center; }}
        .hm-code {{ font-size: 11px; opacity: 0.75; font-weight: 500; white-space: nowrap; }}
        .hm-cells {{ display: grid; grid-template-columns: repeat(14, 1fr); gap: 2px; }}
        .hm-cell {{ aspect-ratio: 1; border-radius: 2px; min-height: 14px; }}
        .hm-avg {{ font-size: 11px; font-weight: 600; text-align: right; color: #cbd5e1; }}
        .hc-dgreen {{ background: #15803d; }}
        .hc-green {{ background: #22c55e; }}
        .hc-amber {{ background: #f59e0b; }}
        .hc-red {{ background: #ef4444; }}
        .hc-none {{ background: rgba(255,255,255,0.06); }}
        .hm-axis {{ display: flex; justify-content: space-between; font-size: 10px; opacity: 0.5; padding: 6px 46px 0 56px; }}
        .hm-legend {{ display: flex; gap: 12px; font-size: 11px; opacity: 0.8; margin-top: 12px; flex-wrap: wrap; justify-content: center; }}
        .hm-leg-item {{ display: flex; align-items: center; gap: 5px; }}
        .hm-swatch {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; }}
'''
src = src.replace(ANCHOR4, ANCHOR4 + CSS, 1)

# ---------------------------------------------------------------------------
# EDIT 4b - the card block itself, inserted right after the YTD card closes.
# Anchor: the unique grade-bars line that ends the YTD card + its </div>
# ---------------------------------------------------------------------------
ANCHOR5 = '''                <div class="grade-bars">{grade_bars_html}</div>
            </div>
            '''
assert src.count(ANCHOR5) == 1, "EDIT4b anchor not unique/found"

CARD = '''                <div class="grade-bars">{grade_bars_html}</div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">\U0001F525 Class Heatmap \u2014 Last 14 Days</span>
                    <span class="card-status status-info">{hm_count} classes</span>
                </div>
                {heatmap_html}
                <div class="hm-axis"><span>{hm_first_lbl}</span><span>{hm_last_lbl}</span></div>
                <div class="hm-legend">
                    <span class="hm-leg-item"><span class="hm-swatch hc-dgreen"></span>97%+</span>
                    <span class="hm-leg-item"><span class="hm-swatch hc-green"></span>95\u201397%</span>
                    <span class="hm-leg-item"><span class="hm-swatch hc-amber"></span>90\u201395%</span>
                    <span class="hm-leg-item"><span class="hm-swatch hc-red"></span>&lt;90%</span>
                </div>
                <a href="/admin/" class="card-link">View registers \u2192</a>
            </div>
            '''
src = src.replace(ANCHOR5, CARD, 1)

# hm_count needs to exist in the f-string scope -> add it next to heatmap_html
ANCHOR6 = "    heatmap_html = build_class_heatmap(hm_matrix, hm_dates)\n"
assert src.count(ANCHOR6) == 1, "hm_count anchor not unique/found"
src = src.replace(ANCHOR6, ANCHOR6 + "    hm_count = len(hm_matrix)\n", 1)

# ---------------------------------------------------------------------------
# Verify + write
# ---------------------------------------------------------------------------
assert src != orig, "No changes applied!"
ast.parse(src)  # raises SyntaxError if broken

with open(PATH, "w") as f:
    f.write(src)

print("OK: 6 edits applied, ast.parse passed.")
print("  - build_class_heatmap helper added")
print("  - heatmap query block added")
print("  - heatmap_html + hm_count + labels added")
print("  - heatmap CSS added")
print("  - Card 4 block inserted after YTD card")
