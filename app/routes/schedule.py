"""
Schedule hub routes - shared schedule reference for all roles.

Today card  : dynamic strip resolved from school_calendar for the current date.
Bell Times  : the 3 static daily bell schedules (type_a / type_b / type_c).
Days Calendar: full-year cycle-day / term / holiday view from school_calendar.

Data sources:
- school_calendar table is authoritative for date -> cycle_day -> bell_schedule
  and for is_school_day / day_type / term. (verified 365 rows, schema_version 11)
- Bell TIMES themselves are static for the year and live here as a constant.
"""

from datetime import date
from flask import Blueprint, render_template, redirect
from app.services.db import get_connection
from app.services.nav import get_nav_header, get_nav_styles

schedule_bp = Blueprint('schedule', __name__, url_prefix='/schedule')

TENANT_ID = "MARAGON"

# Friendly labels for the three bell-schedule types.
SCHEDULE_LABELS = {
    "type_a": "Monday / Wednesday",
    "type_b": "Tuesday / Thursday",
    "type_c": "Friday",
}

# Static bell times for 2026 (source: BELL_TIMES_2026.pdf).
# ASCII-only. The school_calendar column says WHICH type applies on a date;
# these constants supply the TIMES for that type.
BELL_TIMES = {
    "type_a": {
        "label": "Monday / Wednesday",
        "slots": [
            ("Register", "07:30", "07:40"),
            ("Assembly / Worship", "07:40", "08:20"),
            ("Period 1", "08:20", "09:05"),
            ("Period 2", "09:05", "09:50"),
            ("Break", "09:50", "10:10"),
            ("Period 3", "10:10", "10:55"),
            ("Period 4", "10:55", "11:40"),
            ("Period 5", "11:40", "12:25"),
            ("Break", "12:25", "12:45"),
            ("Period 6", "12:45", "13:30"),
            ("Period 7", "13:30", "14:15"),
        ],
    },
    "type_b": {
        "label": "Tuesday / Thursday",
        "slots": [
            ("Register / Test", "07:30", "08:40"),
            ("Period 1", "08:40", "09:22"),
            ("Period 2", "09:22", "10:04"),
            ("Break", "10:04", "10:24"),
            ("Period 3", "10:24", "11:06"),
            ("Period 4", "11:06", "11:48"),
            ("Period 5", "11:48", "12:30"),
            ("Break", "12:30", "12:50"),
            ("Period 6", "12:50", "13:32"),
            ("Period 7", "13:32", "14:15"),
        ],
    },
    "type_c": {
        "label": "Friday",
        "slots": [
            ("Register", "07:30", "07:40"),
            ("Clubs / Mentor", "07:40", "08:30"),
            ("Period 1", "08:30", "09:10"),
            ("Period 2", "09:10", "09:50"),
            ("Period 3", "09:50", "10:30"),
            ("Rec Time", "10:30", "11:05"),
            ("Period 4", "11:05", "11:45"),
            ("Period 5", "11:45", "12:25"),
            ("Period 6", "12:25", "13:05"),
            ("Period 7", "13:05", "13:45"),
        ],
    },
}

# Display order for the three types on the Bell Times page.
BELL_TIMES_ORDER = ["type_a", "type_b", "type_c"]


def _calendar_row(conn, the_date):
    """Return the school_calendar row dict for a date, or None."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM school_calendar WHERE tenant_id = ? AND date = ?",
        (TENANT_ID, the_date),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _next_school_day(conn, after_date):
    """Return the next row with is_school_day = 1 strictly after after_date, or None."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT * FROM school_calendar
        WHERE tenant_id = ? AND date > ? AND is_school_day = 1
        ORDER BY date ASC
        LIMIT 1
        """,
        (TENANT_ID, after_date),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


@schedule_bp.route('/')
def index():
    """Schedule hub: Today card + Reference grid."""
    today_str = date.today().isoformat()

    today_row = None
    next_day = None
    bell = None

    with get_connection() as conn:
        today_row = _calendar_row(conn, today_str)
        if today_row is not None and today_row.get('is_school_day'):
            schedule_type = today_row.get('bell_schedule')
            bell = BELL_TIMES.get(schedule_type)
        else:
            next_day = _next_school_day(conn, today_str)

    today_display = date.today().strftime('%A, %d %B %Y')

    nav_header = get_nav_header("Schedule", "/", "Home")
    nav_styles = get_nav_styles()

    return render_template(
        'schedule/index.html',
        today_row=today_row,
        today_display=today_display,
        next_day=next_day,
        bell=bell,
        nav_header=nav_header,
        nav_styles=nav_styles,
    )


@schedule_bp.route('/bell-times')
def bell_times():
    """The three static daily bell schedules."""
    schedules = [
        {"type": t, "label": BELL_TIMES[t]["label"], "slots": BELL_TIMES[t]["slots"]}
        for t in BELL_TIMES_ORDER
    ]
    nav_header = get_nav_header("Bell Times", "/schedule/", "Schedule")
    nav_styles = get_nav_styles()
    return render_template(
        'schedule/bell_times.html',
        schedules=schedules,
        nav_header=nav_header,
        nav_styles=nav_styles,
    )


@schedule_bp.route('/days-calendar')
def days_calendar():
    """Full-year cycle-day / term / holiday view from school_calendar."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT date, cycle_day, day_type, day_name, weekday,
                   bell_schedule, is_school_day, term
            FROM school_calendar
            WHERE tenant_id = ?
            ORDER BY date ASC
            """,
            (TENANT_ID,),
        )
        rows = [dict(r) for r in cursor.fetchall()]

    # Group by term for a navigable view.
    terms = {}
    for r in rows:
        t = r.get('term')
        terms.setdefault(t, []).append(r)
    grouped = [{"term": t, "days": terms[t]} for t in sorted(terms, key=lambda x: (x is None, x))]

    nav_header = get_nav_header("Days Calendar", "/schedule/", "Schedule")
    nav_styles = get_nav_styles()
    return render_template(
        'schedule/days_calendar.html',
        grouped=grouped,
        nav_header=nav_header,
        nav_styles=nav_styles,
    )
