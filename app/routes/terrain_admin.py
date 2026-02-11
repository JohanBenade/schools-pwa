"""
Terrain duty admin routes - generation UI and reset
"""

from flask import Blueprint, render_template, request, session, redirect
from datetime import date, timedelta
from app.services.db import get_connection
from app.services.duty_generator import preview_duties, generate_duties, clear_duties_in_range

terrain_admin_bp = Blueprint('terrain_admin', __name__, url_prefix='/admin/terrain')

TENANT_ID = "MARAGON"


def _get_default_dates():
    """Calculate default start/end dates for generation."""
    today = date.today()
    weekday = today.weekday()

    this_monday = today - timedelta(days=weekday)
    next_friday = this_monday + timedelta(days=11)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT duty_date FROM duty_roster
            WHERE tenant_id = ? AND duty_date >= ?
            ORDER BY duty_date ASC
        """, (TENANT_ID, today.isoformat()))
        existing_dates = {row['duty_date'] for row in cursor.fetchall()}

    if weekday >= 5:
        search_start = this_monday + timedelta(days=7)
    else:
        search_start = today

    default_start = None
    d = search_start
    while d <= next_friday:
        if d.weekday() < 5 and d.isoformat() not in existing_dates:
            default_start = d
            break
        d += timedelta(days=1)

    if not default_start:
        default_start = search_start

    start_weekday = default_start.weekday()
    days_to_friday = 4 - start_weekday
    if days_to_friday < 0:
        days_to_friday += 7
    default_end = default_start + timedelta(days=days_to_friday)

    if default_end > next_friday:
        default_end = next_friday

    min_date = today if weekday < 5 else this_monday + timedelta(days=7)
    max_date = next_friday

    return default_start, default_end, min_date, max_date


@terrain_admin_bp.route('/generate')
def generate_page():
    """Render the duty generation page."""
    staff_id = session.get('staff_id')
    if not staff_id:
        return redirect('/')

    default_start, default_end, min_date, max_date = _get_default_dates()

    return render_template('admin/generate_duties.html',
        default_start=default_start.isoformat(),
        default_end=default_end.isoformat(),
        min_date=min_date.isoformat(),
        max_date=max_date.isoformat(),
        user_name=session.get('display_name', '')
    )


@terrain_admin_bp.route('/generate/preview', methods=['POST'])
def generate_preview():
    """Return preview HTML via HTMX."""
    staff_id = session.get('staff_id')
    if not staff_id:
        return '<div class="error-msg">Not authenticated</div>', 401

    start_str = request.form.get('start_date', '')
    end_str = request.form.get('end_date', '')

    try:
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    except ValueError:
        return '<div class="error-msg">Invalid date format</div>'

    if start_date > end_date:
        return '<div class="error-msg">Start date must be before end date</div>'

    result = preview_duties(start_date, end_date)

    if result.get('error') == 'duties_exist':
        dates_list = ', '.join(result['existing_dates'])
        return f'''
        <div class="error-msg">
            <p>Duties already exist for: {dates_list}</p>
            <button class="btn btn-warning"
                    onclick="showClearModal('{start_str}', '{end_str}')">
                Clear these dates and regenerate
            </button>
        </div>'''

    if result.get('error'):
        return f'<div class="error-msg">{result["error"]}</div>'

    # Build preview HTML
    days = result['days']
    total = result['total_count']
    html = f'''
    <div class="preview-summary">
        <div class="summary-text">
            {result["terrain_count"]} terrain + {result["homework_count"]} homework = {total} assignments
        </div>
    </div>
    <div class="preview-grid">'''

    for day in days:
        d = day['date']
        try:
            from datetime import datetime
            dt = datetime.strptime(d, '%Y-%m-%d')
            date_display = dt.strftime('%a %d %b')
        except:
            date_display = d

        html += f'<div class="preview-day"><div class="day-header">{date_display}</div>'

        for t in day['terrain']:
            html += f'<div class="preview-row terrain-row"><span class="area-badge">{t["area_name"]}</span> {t["display_name"]}</div>'

        if day['homework']:
            html += f'<div class="preview-row homework-row"><span class="area-badge hw-badge">Homework</span> {day["homework"]}</div>'
        elif day['weekday'].lower() != 'friday':
            html += '<div class="preview-row homework-row muted"><span class="area-badge hw-badge">Homework</span> No one available</div>'

        html += '</div>'

    html += f'''
    </div>
    <div class="preview-actions">
        <button class="btn btn-confirm"
                onclick="showGenerateModal({total}, '{start_str}', '{end_str}')">
            Generate {total} Duties
        </button>
    </div>'''

    return html


@terrain_admin_bp.route('/generate/confirm', methods=['POST'])
def generate_confirm():
    """Execute generation and return success HTML via HTMX."""
    staff_id = session.get('staff_id')
    if not staff_id:
        return '<div class="error-msg">Not authenticated</div>', 401

    start_str = request.form.get('start_date', '')
    end_str = request.form.get('end_date', '')

    try:
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    except ValueError:
        return '<div class="error-msg">Invalid date format</div>'

    result = generate_duties(start_date, end_date)

    if result.get('error'):
        if result['error'] == 'duties_exist':
            return '<div class="error-msg">Duties already exist. Clear first.</div>'
        return f'<div class="error-msg">{result["error"]}</div>'

    return f'''
    <div class="success-area">
        <div class="success-icon">✅</div>
        <div class="success-text">
            Generated {result["total_count"]} duties across {result["days"]} school days
        </div>
        <div class="success-detail">
            {result["terrain_count"]} terrain + {result["homework_count"]} homework
        </div>
        <div class="success-actions">
            <a href="/duty/terrain" class="btn btn-confirm">View Full Roster</a>
        </div>
    </div>'''


@terrain_admin_bp.route('/generate/clear', methods=['POST'])
def generate_clear():
    """Clear duties in range, reset pointers, and return preview via HTMX."""
    staff_id = session.get('staff_id')
    if not staff_id:
        return '<div class="error-msg">Not authenticated</div>', 401

    start_str = request.form.get('start_date', '')
    end_str = request.form.get('end_date', '')

    try:
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    except ValueError:
        return '<div class="error-msg">Invalid date format</div>'

    clear_result = clear_duties_in_range(start_date, end_date)

    result = preview_duties(start_date, end_date)

    if result.get('error') and result['error'] != 'duties_exist':
        return f'<div class="error-msg">{result["error"]}</div>'

    days = result.get('days', [])
    total = result.get('total_count', 0)

    html = f'<div class="cleared-msg">Cleared {clear_result["deleted"]} duties &amp; reset pointers</div>'
    html += f'''
    <div class="preview-summary">
        <div class="summary-text">
            {result.get("terrain_count", 0)} terrain + {result.get("homework_count", 0)} homework = {total} assignments
        </div>
    </div>
    <div class="preview-grid">'''

    for day in days:
        d = day['date']
        try:
            from datetime import datetime
            dt = datetime.strptime(d, '%Y-%m-%d')
            date_display = dt.strftime('%a %d %b')
        except:
            date_display = d

        html += f'<div class="preview-day"><div class="day-header">{date_display}</div>'
        for t in day['terrain']:
            html += f'<div class="preview-row terrain-row"><span class="area-badge">{t["area_name"]}</span> {t["display_name"]}</div>'
        if day['homework']:
            html += f'<div class="preview-row homework-row"><span class="area-badge hw-badge">Homework</span> {day["homework"]}</div>'
        html += '</div>'

    html += f'''
    </div>
    <div class="preview-actions">
        <button class="btn btn-confirm"
                onclick="showGenerateModal({total}, '{start_str}', '{end_str}')">
            Generate {total} Duties
        </button>
    </div>'''

    return html


@terrain_admin_bp.route('/reset')
def reset_terrain():
    """Clear ALL terrain duties and reset pointers (testing only)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM duty_roster WHERE tenant_id = ?", (TENANT_ID,))
        deleted = cursor.rowcount
        cursor.execute("""
            UPDATE terrain_config 
            SET pointer_index = 0, homework_pointer_index = 0, updated_at = datetime('now')
            WHERE tenant_id = ?
        """, (TENANT_ID,))
        conn.commit()

    from flask import jsonify
    return jsonify({'success': True, 'deleted': deleted, 'message': 'All duties cleared, pointers reset'})
