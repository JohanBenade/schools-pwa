"""
Management Dashboard - Principal, Deputy, Admin view
"""

from flask import Blueprint, session, redirect, request
from datetime import date
from app.services.db import get_connection
from app.services.nav import get_role_label

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')

TENANT_ID = "MARAGON"


def build_sparkline(daily_data, width=320, height=80, padding=8):
    """Generate inline SVG sparkline from list of (date_str, pct) tuples."""
    if not daily_data:
        return ''
    pcts = [d[1] for d in daily_data]
    min_pct = max(0, min(pcts) - 2)
    max_pct = min(100, max(pcts) + 2)
    range_pct = max_pct - min_pct or 1
    inner_w = width - 2 * padding
    inner_h = height - 2 * padding
    n = len(daily_data)
    points = []
    for i, (_, pct) in enumerate(daily_data):
        x = padding + (i / max(1, n - 1)) * inner_w
        y = padding + (1 - (pct - min_pct) / range_pct) * inner_h
        points.append(f"{x:.1f},{y:.1f}")
    pts_str = ' '.join(points)
    area_pts = pts_str + f" {padding + inner_w:.1f},{padding + inner_h:.1f} {padding:.1f},{padding + inner_h:.1f}"
    return (
        f'<svg viewBox="0 0 {width} {height}" '
        f'style="width:100%;height:{height}px;display:block;" '
        f'preserveAspectRatio="none">'
        '<defs><linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#06b6d4" stop-opacity="0.35"/>'
        '<stop offset="100%" stop-color="#06b6d4" stop-opacity="0"/>'
        '</linearGradient></defs>'
        f'<polygon points="{area_pts}" fill="url(#sparkFill)"/>'
        f'<polyline points="{pts_str}" fill="none" stroke="#06b6d4" stroke-width="2" '
        'stroke-linejoin="round" stroke-linecap="round"/>'
        '</svg>'
    )


def build_grade_bars(grade_data):
    """HTML grade bars from list of (grade_num, pct) tuples."""
    if not grade_data:
        return ''
    rows = []
    for grade_num, pct in grade_data:
        rows.append(
            f'<div class="grade-bar">'
            f'<span class="grade-label">Gr {grade_num}</span>'
            f'<span class="grade-pct">{pct:.1f}%</span>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%"></div></div>'
            f'</div>'
        )
    return ''.join(rows)


def format_date_short(date_str):
    """'2026-01-14' -> '14 Jan'"""
    try:
        from datetime import datetime
        d = datetime.strptime(date_str, '%Y-%m-%d')
        return d.strftime('%-d %b')
    except Exception:
        return date_str


def build_chronic_rows(learners):
    if not learners:
        return '<div class="detail-list"><div class="detail-item" style="color:#22c55e;">No chronic absentees</div></div>'
    rows = []
    for l in learners:
        full = f"{l['first_name']} {l['surname']}"
        tier = 'critical' if l['absent_count'] >= 20 else 'high'
        rows.append(
            f'<a href="/dashboard/learner/{l["id"]}/?from=chronic" class="absentee-row">'
            f'<span class="absentee-name"><span class="dot dot-{tier}" style="margin-right:8px;"></span>{full}</span>'
            f'<span class="absentee-meta">{l["group_name"] or "—"} &middot; {l["absent_count"]} days</span>'
            f'</a>'
        )
    return '<div class="absentee-list">' + ''.join(rows) + '</div>'


def build_attendance_strip(history):
    if not history:
        return '<div style="opacity:0.6;text-align:center;padding:20px;">No attendance data</div>'
    colors = {'Present': '#22c55e', 'Absent': '#ef4444', 'Late': '#f59e0b', 'Left_Early': '#94a3b8'}
    default = 'rgba(255,255,255,0.1)'
    n = len(history)
    cell_w = 10
    gap = 2
    h = 32
    w = n * (cell_w + gap)
    parts = [f'<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none" style="width:100%;height:{h}px;display:block;">']
    for i, (date_str, status) in enumerate(history):
        x = i * (cell_w + gap)
        color = colors.get(status, default)
        parts.append(f'<rect x="{x}" y="0" width="{cell_w}" height="{h}" rx="2" fill="{color}"><title>{date_str}: {status}</title></rect>')
    parts.append('</svg>')
    return ''.join(parts)


def build_insight_line(ytd_pct, daily_data, chronic_count, worst_grade_num, worst_grade_count):
    """One computed summary sentence: health + trend + top watch item."""
    # health word from ytd
    if ytd_pct >= 95:
        health = 'healthy'
    elif ytd_pct >= 90:
        health = 'steady'
    else:
        health = 'under pressure'
    # trend: last third vs first third of daily pcts
    trend = 'holding steady'
    pcts = [p for _, p in daily_data]
    if len(pcts) >= 6:
        third = max(1, len(pcts) // 3)
        early = sum(pcts[:third]) / third
        late = sum(pcts[-third:]) / third
        if late - early >= 1.0:
            trend = 'trending up'
        elif early - late >= 1.0:
            trend = 'trending down'
    lead = f"Attendance is {health} at {ytd_pct:.1f}%, {trend}."
    # watch clause
    watch = ''
    if chronic_count > 0:
        plural = 's' if chronic_count != 1 else ''
        grade_bit = f", most in Grade {worst_grade_num}" if worst_grade_num else ''
        watch = f" Watch: {chronic_count} learner{plural} with chronic absence{grade_bit}."
    return lead + watch


def build_pattern_caption(daily_data):
    """Compute a true caption from the data: weakest weekday + worst week/month."""
    from datetime import datetime
    parsed = []
    for d, p in daily_data:
        try:
            parsed.append((datetime.strptime(d, '%Y-%m-%d'), p))
        except Exception:
            continue
    if not parsed:
        return 'Each square = one school day.'
    # weakest weekday (Mon-Fri only)
    wd_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    wd_sum = [0.0] * 5
    wd_cnt = [0] * 5
    for dt, p in parsed:
        wd = dt.weekday()
        if wd <= 4:
            wd_sum[wd] += p
            wd_cnt[wd] += 1
    wd_avg = [(wd_sum[i] / wd_cnt[i]) if wd_cnt[i] else 100.0 for i in range(5)]
    weakest_i = min(range(5), key=lambda i: wd_avg[i])
    overall = sum(p for _, p in parsed) / len(parsed)
    weakest_clause = ''
    if wd_avg[weakest_i] < overall - 0.5:
        weakest_clause = f"{wd_names[weakest_i]}s run slightly lower"
    # worst ISO week -> month label
    week_sum = {}
    week_cnt = {}
    week_anydate = {}
    for dt, p in parsed:
        iso = dt.isocalendar()
        k = (iso[0], iso[1])
        week_sum[k] = week_sum.get(k, 0.0) + p
        week_cnt[k] = week_cnt.get(k, 0) + 1
        week_anydate.setdefault(k, dt)
    worst_k = min(week_sum, key=lambda k: week_sum[k] / week_cnt[k])
    worst_avg = week_sum[worst_k] / week_cnt[worst_k]
    worst_month = week_anydate[worst_k].strftime('%b')
    dip_clause = ''
    if worst_avg < overall - 3:
        dip_clause = f"the red column is the {worst_month} dip"
    parts = ['Each square = one school day.']
    tail = '; '.join([c for c in [weakest_clause, dip_clause] if c])
    if tail:
        parts.append(tail[0].upper() + tail[1:] + '.')
    return ' '.join(parts)


def build_year_pixels(daily_data):
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


@dashboard_bp.route('/')
def index():
    user_role = session.get('role', 'teacher')
    if user_role not in ['principal', 'deputy', 'admin', 'management']:
        return redirect('/')
    
    today = date.today()
    today_str = today.isoformat()
    today_display = today.strftime('%A, %d %B %Y')
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM mentor_group WHERE tenant_id = ?', (TENANT_ID,))
        total_groups = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM attendance WHERE tenant_id = ? AND date = ?', (TENANT_ID, today_str))
        submitted_count = cursor.fetchone()[0]
        
        pending_count = total_groups - submitted_count
        
        cursor.execute('''
            SELECT mg.group_name
            FROM mentor_group mg
            WHERE mg.tenant_id = ? AND mg.id NOT IN (
                SELECT mentor_group_id FROM attendance WHERE date = ? AND tenant_id = ?
            )
            ORDER BY mg.group_name
            LIMIT 5
        ''', (TENANT_ID, today_str, TENANT_ID))
        pending_classes = [row['group_name'] for row in cursor.fetchall()]
        
        cursor.execute('''
            SELECT COUNT(*) FROM attendance_entry ae
            JOIN attendance a ON ae.attendance_id = a.id
            WHERE a.date = ? AND a.tenant_id = ? AND ae.status = 'Absent'
        ''', (today_str, TENANT_ID))
        absent_learners = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM learner WHERE tenant_id = ? AND COALESCE(is_active, 1) = 1', (TENANT_ID,))
        total_enrolled = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(*) FROM attendance_entry ae JOIN attendance a ON ae.attendance_id = a.id
            WHERE a.date = ? AND a.tenant_id = ?
        ''', (today_str, TENANT_ID))
        captured_today = cursor.fetchone()[0] or 0
        today_pct = ((captured_today - absent_learners) / captured_today * 100) if captured_today else 0
        
        cursor.execute('''
            SELECT g.grade_number, COUNT(*) AS absent FROM attendance_entry ae
            JOIN attendance a ON ae.attendance_id = a.id
            JOIN learner l ON l.id = ae.learner_id
            JOIN grade g ON g.id = l.grade_id
            WHERE a.date = ? AND a.tenant_id = ? AND ae.status = 'Absent'
            GROUP BY g.grade_number ORDER BY g.grade_number
        ''', (today_str, TENANT_ID))
        grade_breakdown_today = [(r['grade_number'], r['absent']) for r in cursor.fetchall()]
        
        cursor.execute('''
            SELECT ea.*, s.display_name as triggered_by_name,
                   (SELECT COUNT(*) FROM emergency_response er WHERE er.alert_id = ea.id) as responder_count
            FROM emergency_alert ea
            LEFT JOIN staff s ON ea.triggered_by_id = s.id
            WHERE ea.tenant_id = ? AND ea.status = 'Active'
            ORDER BY ea.triggered_at DESC LIMIT 1
        ''', (TENANT_ID,))
        row = cursor.fetchone()
        active_emergency = dict(row) if row else None
        
        cursor.execute('''
            SELECT a.*, s.display_name as teacher_name,
                   (SELECT COUNT(*) FROM substitute_request sr 
                    WHERE sr.absence_id = a.id AND sr.status = 'Assigned') as covered_count,
                   (SELECT COUNT(*) FROM substitute_request sr WHERE sr.absence_id = a.id) as total_periods
            FROM absence a
            JOIN staff s ON a.staff_id = s.id
            WHERE a.absence_date = ? AND a.tenant_id = ?
            ORDER BY a.reported_at DESC
        ''', (today_str, TENANT_ID))
        absences = [dict(row) for row in cursor.fetchall()]
        
        total_absences = len(absences)
        gaps = sum(a['total_periods'] - a['covered_count'] for a in absences)
        
        cursor.execute('''
            SELECT 
              SUM(CASE WHEN ae.status='Present' THEN 1 ELSE 0 END) * 100.0 / NULLIF(COUNT(*),0) AS ytd_pct,
              COUNT(DISTINCT a.date) AS days_counted
            FROM attendance_entry ae JOIN attendance a ON a.id = ae.attendance_id
            WHERE a.tenant_id = ?
        ''', (TENANT_ID,))
        row = cursor.fetchone()
        ytd_pct = row['ytd_pct'] or 0
        days_counted = row['days_counted'] or 0
        
        cursor.execute('''
            SELECT a.date,
              SUM(CASE WHEN ae.status='Present' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS pct
            FROM attendance a JOIN attendance_entry ae ON ae.attendance_id = a.id
            WHERE a.tenant_id = ?
            GROUP BY a.date ORDER BY a.date
        ''', (TENANT_ID,))
        daily_attendance = [(r['date'], r['pct']) for r in cursor.fetchall()]
        
        cursor.execute('''
            SELECT g.grade_number,
              SUM(CASE WHEN ae.status='Present' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS pct
            FROM attendance a
            JOIN attendance_entry ae ON ae.attendance_id = a.id
            JOIN learner l ON l.id = ae.learner_id
            JOIN grade g ON g.id = l.grade_id
            WHERE a.tenant_id = ?
            GROUP BY g.grade_number ORDER BY g.grade_number
        ''', (TENANT_ID,))
        grade_data = [(r['grade_number'], r['pct']) for r in cursor.fetchall()]
        
        cursor.execute('''
            SELECT 
              l.id, l.first_name, l.surname, mg.group_name, g.grade_number,
              SUM(CASE WHEN ae.status='Absent' THEN 1 ELSE 0 END) AS absent_count
            FROM learner l
            JOIN attendance_entry ae ON ae.learner_id = l.id
            JOIN attendance a ON a.id = ae.attendance_id
            LEFT JOIN mentor_group mg ON mg.id = l.mentor_group_id
            LEFT JOIN grade g ON g.id = l.grade_id
            WHERE l.tenant_id = ? AND a.tenant_id = ? AND COALESCE(l.is_active, 1) = 1
            GROUP BY l.id
            HAVING SUM(CASE WHEN ae.status='Absent' THEN 1 ELSE 0 END) >= 15
            ORDER BY absent_count DESC
        ''', (TENANT_ID, TENANT_ID))
        chronic_all = [dict(r) for r in cursor.fetchall()]
    
    if grade_breakdown_today:
        gb_parts = [f'Gr {g}: {n}' for g, n in grade_breakdown_today]
        grade_breakdown_html = '<div class="grade-breakdown">' + ' &middot; '.join(gb_parts) + '</div>'
    else:
        grade_breakdown_html = ''
    if captured_today == 0:
        today_pct_class = 'status-info'
        today_pct_display = '—'
    elif today_pct >= 95:
        today_pct_class = 'status-green'
        today_pct_display = f'{today_pct:.1f}%'
    elif today_pct >= 90:
        today_pct_class = 'status-yellow'
        today_pct_display = f'{today_pct:.1f}%'
    else:
        today_pct_class = 'status-red'
        today_pct_display = f'{today_pct:.1f}%'
    
    emergency_html = ""
    if active_emergency:
        emergency_html = f'''
            <div class="big-number">1</div>
            <div class="big-label">active emergency</div>
            <div class="detail-list">
                <div class="detail-item">📍 {active_emergency['location_display'] or 'Unknown'}</div>
                <div class="detail-item">🏷️ {active_emergency['alert_type']}</div>
                <div class="detail-item">👤 {active_emergency['triggered_by_name']}</div>
                <div class="detail-item">🙋 {active_emergency['responder_count']} responding</div>
            </div>
            <a href="/emergency/" class="card-link">View Emergency →</a>
        '''
    else:
        emergency_html = '''
            <div class="big-number" style="color: #22c55e;">✓</div>
            <div class="big-label">No active emergencies</div>
            <a href="/emergency/" class="card-link">Emergency Center →</a>
        '''
    
    absences_html = ""
    if absences:
        rows = ''.join(f'<div class="absence-row"><span class="absence-name">{a["teacher_name"]}</span><span class="absence-status">{a["covered_count"]}/{a["total_periods"]}</span></div>' for a in absences[:3])
        absences_html = f'<div class="detail-list">{rows}</div>'
    else:
        absences_html = '<div class="detail-list"><div class="detail-item" style="color: #22c55e;">✓ No absences reported</div></div>'
    
    pending_html = ""
    if pending_classes:
        names = ', '.join(pending_classes[:3]) + ('...' if len(pending_classes) > 3 else '')
        pending_html = f'<div class="detail-list"><div class="detail-item">⏳ {names}</div></div>'
    
    sparkline_svg = build_sparkline(daily_attendance)
    year_pixels_html = build_year_pixels(daily_attendance)
    pattern_caption = build_pattern_caption(daily_attendance)
    grade_bars_html = build_grade_bars(grade_data)
    from collections import Counter
    flagged_total = len(chronic_all)
    critical_count = sum(1 for x in chronic_all if x['absent_count'] >= 20)
    high_count = flagged_total - critical_count
    grade_counts = Counter(x['grade_number'] for x in chronic_all if x.get('grade_number'))
    if grade_counts:
        worst_grade_num, worst_grade_count = grade_counts.most_common(1)[0]
    else:
        worst_grade_num, worst_grade_count = None, 0
    insight_line = build_insight_line(ytd_pct, daily_attendance, flagged_total, worst_grade_num, worst_grade_count)
    if flagged_total > 0:
        critical_flex = max(1, critical_count)
        high_flex = max(1, high_count)
        worst_html = f'<div class="detail-list"><div class="detail-item">Most affected: <strong>Grade {worst_grade_num}</strong> &middot; {worst_grade_count} learners</div></div>' if worst_grade_num else ''
        chronic_card_body = (
            f'<div class="big-number">{flagged_total}</div>'
            f'<div class="big-label">learners with 15+ days absent</div>'
            f'<div class="tier-bar"><div class="tier-segment tier-critical" style="flex:{critical_flex};"></div><div class="tier-segment tier-high" style="flex:{high_flex};"></div></div>'
            f'<div class="tier-legend"><div class="tier-label"><span class="dot dot-critical"></span>{critical_count} critical (20+ days)</div><div class="tier-label"><span class="dot dot-high"></span>{high_count} high (15-19 days)</div></div>'
            f'{worst_html}'
            f'<a href="/dashboard/chronic-absentees/" class="card-link">View all {flagged_total} &rarr;</a>'
        )
    else:
        chronic_card_body = '<div class="big-number" style="color:#22c55e;">&check;</div><div class="big-label">No chronic absenteeism</div>'
    if daily_attendance:
        first_lbl = format_date_short(daily_attendance[0][0])
        mid_lbl = format_date_short(daily_attendance[len(daily_attendance)//2][0])
        last_lbl = format_date_short(daily_attendance[-1][0])
    else:
        first_lbl = mid_lbl = last_lbl = ''
    ytd_subtitle = f'across {days_counted} school days' if days_counted else 'no data yet'
    
    user_name = session.get('display_name', '')
    user_role_label = get_role_label(session.get('role'))
    
    return f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - SchoolOps</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); min-height: 100vh; padding: 80px 20px 40px; color: white; }}
        .container {{ max-width: 600px; margin: 0 auto; }}
        .user-bar {{ position: fixed; top: 0; left: 0; right: 0; background: rgba(15,23,42,0.95); padding: 12px 20px; font-size: 14px; color: white; z-index: 100; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 10px rgba(0,0,0,0.3); border-bottom: 1px solid rgba(255,255,255,0.1); }}
        .user-bar a {{ color: white; text-decoration: none; opacity: 0.85; }}
        .header-date {{ font-size: 14px; opacity: 0.7; text-align: center; margin-top: 8px; margin-bottom: 16px; }}
        .insight-line {{ font-size: 16px; line-height: 1.5; text-align: center; margin-bottom: 24px; opacity: 0.92; font-weight: 500; }}
        .cards {{ display: flex; flex-direction: column; gap: 16px; }}
        .card {{ background: rgba(255,255,255,0.1); border-radius: 16px; padding: 20px; }}
        .card-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }}
        .card-title {{ font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.8; }}
        .card-status {{ padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600; }}
        .status-green {{ background: #22c55e; }}
        .status-yellow {{ background: #eab308; color: #000; }}
        .status-red {{ background: #ef4444; }}
        .status-info {{ background: #06b6d4; color: #022f37; }}
        .big-number {{ font-size: 48px; font-weight: 700; line-height: 1; }}
        .big-label {{ font-size: 14px; opacity: 0.7; margin-top: 4px; }}
        .stat-row {{ display: flex; gap: 24px; margin-top: 16px; }}
        .stat {{ flex: 1; }}
        .stat-value {{ font-size: 24px; font-weight: 600; }}
        .stat-label {{ font-size: 12px; opacity: 0.6; }}
        .detail-list {{ margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.1); }}
        .detail-item {{ font-size: 13px; padding: 6px 0; opacity: 0.8; }}
        .grade-breakdown {{ font-size: 13px; opacity: 0.85; margin-top: 12px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,0.1); text-align: center; }}
        .card-link {{ display: block; text-align: center; margin-top: 16px; padding: 12px; background: rgba(255,255,255,0.1); border-radius: 8px; color: white; text-decoration: none; font-size: 14px; }}
        .card-link:hover {{ background: rgba(255,255,255,0.15); }}
        .sparkline-wrap {{ margin: 16px 0 4px; }}
        .sparkline-axis {{ display: flex; justify-content: space-between; font-size: 10px; opacity: 0.5; padding: 4px 4px 0; }}
        .grade-bars {{ display: flex; flex-direction: column; gap: 10px; margin-top: 16px; padding-top: 16px; border-top: 1px solid rgba(255,255,255,0.1); }}
        .grade-bar {{ display: grid; grid-template-columns: 44px 56px 1fr; gap: 12px; align-items: center; font-size: 13px; }}
        .grade-label {{ opacity: 0.7; font-weight: 500; }}
        .grade-pct {{ font-weight: 600; text-align: right; color: #22d3ee; }}
        .bar-track {{ background: rgba(255,255,255,0.08); height: 8px; border-radius: 4px; overflow: hidden; }}
        .bar-fill {{ background: linear-gradient(90deg, #0891b2, #06b6d4, #22d3ee); height: 100%; border-radius: 4px; }}
        .year-pixels {{ display: flex; flex-direction: column; gap: 3px; margin-top: 16px; }}
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
        .yp-caption {{ font-size: 11px; opacity: 0.6; text-align: center; margin-top: 10px; line-height: 1.4; }}
        .emergency-active {{ background: linear-gradient(135deg, #dc2626 0%, #991b1b 100%); animation: pulse-border 2s infinite; }}
        @keyframes pulse-border {{ 0%, 100% {{ box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }} 50% {{ box-shadow: 0 0 0 8px rgba(239, 68, 68, 0); }} }}
        .tier-bar {{ display: flex; height: 8px; border-radius: 4px; overflow: hidden; margin: 16px 0 8px; gap: 2px; }}
        .tier-segment {{ height: 100%; }}
        .tier-critical {{ background: #ef4444; }}
        .tier-high {{ background: #f59e0b; }}
        .tier-legend {{ display: flex; gap: 16px; font-size: 12px; opacity: 0.85; margin-bottom: 8px; flex-wrap: wrap; }}
        .tier-label {{ display: flex; align-items: center; gap: 6px; }}
        .dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
        .dot-critical {{ background: #ef4444; }}
        .dot-high {{ background: #f59e0b; }}
        .absentee-list {{ display: flex; flex-direction: column; gap: 4px; margin-top: 12px; }}
        .absentee-row {{ display: flex; justify-content: space-between; align-items: center; padding: 12px; background: rgba(255,255,255,0.04); border-radius: 8px; color: white; text-decoration: none; transition: background 0.15s; }}
        .absentee-row:hover {{ background: rgba(255,255,255,0.08); }}
        .absentee-row:active {{ background: rgba(255,255,255,0.12); }}
        .absentee-name {{ font-weight: 500; font-size: 14px; display: flex; align-items: center; }}
        .absentee-meta {{ font-size: 12px; opacity: 0.7; }}
        .absence-row {{ display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.1); }}
        .absence-row:last-child {{ border-bottom: none; }}
        .absence-name {{ font-weight: 500; }}
        .absence-status {{ font-size: 12px; padding: 2px 8px; border-radius: 8px; background: #22c55e; }}
    </style>
</head>
<body>
    <div class="user-bar">
        <a href="/tools/">⊞ Operations</a>
        <span>🏛️ {user_name} · {user_role_label}</span>
    </div>
    <div class="container">
        <div class="header-date">{today_display}</div>
        <div class="insight-line">{insight_line}</div>
        
        <div class="cards">
            <div class="card">
                <div class="card-header">
                    <span class="card-title">🗓️ Attendance — Daily Pattern</span>
                    <span class="card-status status-info">{days_counted} days</span>
                </div>
                {year_pixels_html}
                <div class="yp-legend">
                    <span class="yp-leg-item"><span class="yp-swatch yp-green"></span>95%+</span>
                    <span class="yp-leg-item"><span class="yp-swatch yp-amber"></span>90–95%</span>
                    <span class="yp-leg-item"><span class="yp-swatch yp-red"></span>&lt;90%</span>
                </div>
                <div class="yp-caption">{pattern_caption}</div>
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">📊 Attendance — Year to Date</span>
                    <span class="card-status status-info">{days_counted} days</span>
                </div>
                <div class="big-number" style="color:#22c55e;">{ytd_pct:.1f}%</div>
                <div class="big-label">{ytd_subtitle}</div>
                <div class="sparkline-wrap">{sparkline_svg}</div>
                <div class="sparkline-axis">
                    <span>{first_lbl}</span>
                    <span>{mid_lbl}</span>
                    <span>{last_lbl}</span>
                </div>
                <div class="grade-bars">{grade_bars_html}</div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <span class="card-title">⚠️ Chronic Absenteeism</span>
                    <span class="card-status status-yellow">{flagged_total}</span>
                </div>
                {chronic_card_body}
            </div>

            <div class="card">
                <div class="card-header">
                    <span class="card-title">📋 Registers — Today</span>
                    <span class="card-status {'status-green' if pending_count == 0 else 'status-yellow' if pending_count <= 3 else 'status-red'}">{'All In' if pending_count == 0 else f'{pending_count} Pending'}</span>
                </div>
                <div class="big-number">{submitted_count}/{total_groups}</div>
                <div class="big-label">registers submitted</div>
                {pending_html}
                <a href="/admin/" class="card-link">View registers →</a>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <span class="card-title">🎒 Absent Today</span>
                    <span class="card-status {today_pct_class}">{today_pct_display}</span>
                </div>
                <div class="big-number">{absent_learners}</div>
                <div class="big-label">learners absent &middot; of {total_enrolled} enrolled</div>
                {grade_breakdown_html}
                <a href="/absences/learners" class="card-link">Who's out →</a>
            </div>
            
            <div class="card {'emergency-active' if active_emergency else ''}">
                <div class="card-header">
                    <span class="card-title">🚨 Emergencies</span>
                    <span class="card-status {'status-red' if active_emergency else 'status-green'}">{'ACTIVE' if active_emergency else 'All Clear'}</span>
                </div>
                {emergency_html}
            </div>
            
            <div class="card">
                <div class="card-header">
                    <span class="card-title">👩‍🏫 Substitute Coverage</span>
                    <span class="card-status {'status-green' if gaps == 0 else 'status-yellow'}">{'All Covered' if gaps == 0 else f'{gaps} Gap{"s" if gaps != 1 else ""}'}</span>
                </div>
                <div class="big-number">{total_absences}</div>
                <div class="big-label">teacher{'s' if total_absences != 1 else ''} absent today</div>
                {absences_html}
                <a href="/substitute/overview" class="card-link">Substitute Overview →</a>
            </div>
        </div>
    </div>
</body>
</html>
'''



@dashboard_bp.route('/chronic-absentees/')
def chronic_absentees_list():
    user_role = session.get('role', 'teacher')
    if user_role not in ['principal', 'deputy', 'admin', 'management']:
        return redirect('/')
    user_name = session.get('display_name', '')
    user_role_label = get_role_label(session.get('role'))
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
              l.id, l.first_name, l.surname, mg.group_name, g.grade_number,
              SUM(CASE WHEN ae.status='Absent' THEN 1 ELSE 0 END) AS absent_count
            FROM learner l
            JOIN attendance_entry ae ON ae.learner_id = l.id
            JOIN attendance a ON a.id = ae.attendance_id
            LEFT JOIN mentor_group mg ON mg.id = l.mentor_group_id
            LEFT JOIN grade g ON g.id = l.grade_id
            WHERE l.tenant_id = ? AND a.tenant_id = ? AND COALESCE(l.is_active, 1) = 1
            GROUP BY l.id
            HAVING SUM(CASE WHEN ae.status='Absent' THEN 1 ELSE 0 END) >= 15
            ORDER BY absent_count DESC
        ''', (TENANT_ID, TENANT_ID))
        chronic = [dict(r) for r in cursor.fetchall()]
    total = len(chronic)
    rows_html = build_chronic_rows(chronic)
    plural = 's' if total != 1 else ''
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chronic Absentees - SchoolOps</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); min-height: 100vh; padding: 60px 20px 40px; color: white; }}
.container {{ max-width: 600px; margin: 0 auto; }}
.user-bar {{ position: fixed; top: 0; left: 0; right: 0; background: rgba(15,23,42,0.95); padding: 12px 20px; font-size: 14px; color: white; z-index: 100; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 10px rgba(0,0,0,0.3); border-bottom: 1px solid rgba(255,255,255,0.1); }}
.user-bar a {{ color: white; text-decoration: none; opacity: 0.85; }}
.page-header {{ text-align: center; margin-bottom: 24px; }}
.page-title {{ font-size: 24px; font-weight: 700; }}
.page-subtitle {{ font-size: 13px; opacity: 0.7; margin-top: 6px; }}
.page-count {{ font-size: 14px; opacity: 0.85; margin-top: 8px; }}
.absentee-list {{ display: flex; flex-direction: column; gap: 6px; }}
.absentee-row {{ display: flex; justify-content: space-between; align-items: center; padding: 14px; background: rgba(255,255,255,0.06); border-radius: 8px; color: white; text-decoration: none; transition: background 0.15s; }}
.absentee-row:hover {{ background: rgba(255,255,255,0.10); }}
.absentee-row:active {{ background: rgba(255,255,255,0.14); }}
.absentee-name {{ font-weight: 500; font-size: 15px; display: flex; align-items: center; }}
.absentee-meta {{ font-size: 13px; opacity: 0.7; }}
.dot {{ width: 8px; height: 8px; border-radius: 50%; display: inline-block; }}
.dot-critical {{ background: #ef4444; }}
.dot-high {{ background: #f59e0b; }}
</style></head><body>
<div class="user-bar">
    <a href="/dashboard/">&larr; Dashboard</a>
    <span>&#x1F3DB; {user_name} &middot; {user_role_label}</span>
</div>
<div class="container">
    <div class="page-header">
        <div class="page-title">&#9888; Chronic Absentees</div>
        <div class="page-subtitle">15+ days absent &middot; year-to-date</div>
        <div class="page-count">{total} learner{plural} flagged</div>
    </div>
    {rows_html}
</div></body></html>'''


@dashboard_bp.route('/learner/<learner_id>/')
def learner_detail(learner_id):
    user_role = session.get('role', 'teacher')
    if user_role not in ['principal', 'deputy', 'admin', 'management']:
        return redirect('/')
    user_name = session.get('display_name', '')
    user_role_label = get_role_label(session.get('role'))
    from_page = request.args.get('from', '')
    if from_page == 'chronic':
        back_url = '/dashboard/chronic-absentees/'
        back_label = 'Chronic Absentees'
    else:
        back_url = '/dashboard/'
        back_label = 'Dashboard'
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT l.*, mg.group_name, g.grade_number
            FROM learner l
            LEFT JOIN mentor_group mg ON mg.id = l.mentor_group_id
            LEFT JOIN grade g ON g.id = l.grade_id
            WHERE l.id = ? AND l.tenant_id = ?
        ''', (learner_id, TENANT_ID))
        row = cursor.fetchone()
        if not row:
            return redirect('/dashboard/')
        learner = dict(row)
        cursor.execute('''
            SELECT a.date, ae.status
            FROM attendance_entry ae
            JOIN attendance a ON a.id = ae.attendance_id
            WHERE ae.learner_id = ? AND a.tenant_id = ?
            ORDER BY a.date
        ''', (learner_id, TENANT_ID))
        history = [(r['date'], r['status']) for r in cursor.fetchall()]
    total = len(history)
    present = sum(1 for _, s in history if s == 'Present')
    absent = sum(1 for _, s in history if s == 'Absent')
    pct = (present / total * 100) if total else 0
    full_name = f"{learner['first_name']} {learner['surname']}"
    grade_label = f"Grade {learner.get('grade_number')}" if learner.get('grade_number') else ''
    group_label = learner.get('group_name') or ''
    meta = ' · '.join([p for p in [grade_label, group_label] if p])
    strip_html = build_attendance_strip(history)
    first_date = format_date_short(history[0][0]) if history else ''
    last_date = format_date_short(history[-1][0]) if history else ''
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{full_name} - SchoolOps</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); min-height: 100vh; padding: 60px 20px 40px; color: white; }}
.container {{ max-width: 600px; margin: 0 auto; }}
.user-bar {{ position: fixed; top: 0; left: 0; right: 0; background: rgba(15,23,42,0.95); padding: 12px 20px; font-size: 14px; color: white; z-index: 100; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 2px 10px rgba(0,0,0,0.3); border-bottom: 1px solid rgba(255,255,255,0.1); }}
.user-bar a {{ color: white; text-decoration: none; opacity: 0.85; }}
.learner-header {{ text-align: center; margin-bottom: 24px; }}
.learner-name {{ font-size: 28px; font-weight: 700; }}
.learner-meta {{ font-size: 14px; opacity: 0.7; margin-top: 4px; }}
.card {{ background: rgba(255,255,255,0.1); border-radius: 16px; padding: 20px; margin-bottom: 16px; }}
.card-title {{ font-size: 14px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.8; margin-bottom: 16px; }}
.stat-row {{ display: flex; gap: 12px; }}
.stat {{ flex: 1; text-align: center; }}
.stat-value {{ font-size: 28px; font-weight: 700; }}
.stat-label {{ font-size: 11px; opacity: 0.7; margin-top: 2px; }}
.strip-axis {{ display: flex; justify-content: space-between; font-size: 11px; opacity: 0.5; margin-top: 8px; }}
.legend {{ display: flex; gap: 16px; justify-content: center; margin-top: 12px; font-size: 12px; opacity: 0.7; flex-wrap: wrap; }}
.legend-item {{ display: flex; align-items: center; gap: 6px; }}
.legend-swatch {{ width: 10px; height: 10px; border-radius: 2px; }}
</style></head><body>
<div class="user-bar">
    <a href="{back_url}">&larr; {back_label}</a>
    <span>&#x1F3DB; {user_name} &middot; {user_role_label}</span>
</div>
<div class="container">
    <div class="learner-header">
        <div class="learner-name">{full_name}</div>
        <div class="learner-meta">{meta}</div>
    </div>
    <div class="card">
        <div class="card-title">&#x1F4CA; Attendance Summary</div>
        <div class="stat-row">
            <div class="stat"><div class="stat-value" style="color:#22d3ee;">{pct:.1f}%</div><div class="stat-label">attendance</div></div>
            <div class="stat"><div class="stat-value">{present}</div><div class="stat-label">present</div></div>
            <div class="stat"><div class="stat-value" style="color:#ef4444;">{absent}</div><div class="stat-label">absent</div></div>
            <div class="stat"><div class="stat-value">{total}</div><div class="stat-label">days</div></div>
        </div>
    </div>
    <div class="card">
        <div class="card-title">&#x1F4C5; {total}-Day Attendance Strip</div>
        {strip_html}
        <div class="strip-axis"><span>{first_date}</span><span>{last_date}</span></div>
        <div class="legend">
            <div class="legend-item"><div class="legend-swatch" style="background:#22c55e;"></div>Present</div>
            <div class="legend-item"><div class="legend-swatch" style="background:#ef4444;"></div>Absent</div>
            <div class="legend-item"><div class="legend-swatch" style="background:#94a3b8;"></div>Left Early</div>
        </div>
    </div>
</div></body></html>'''
