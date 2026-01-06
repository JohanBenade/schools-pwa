"""
SchoolOps SQLite Database Service
Handles all transactional data (high-frequency writes)
Reference data remains in Notion
"""

import sqlite3
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

# Database path - configurable via environment
DB_PATH = Path(__file__).parent.parent / "data" / "schoolops.db"


def get_db_path() -> Path:
    """Get database path, creating directory if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DB_PATH


def init_db():
    """Initialize database with schema."""
    schema_path = Path(__file__).parent / "schema.sql"
    
    with get_connection() as conn:
        with open(schema_path, 'r') as f:
            conn.executescript(f.read())
        conn.commit()
    
    print(f"Database initialized: {get_db_path()}")


@contextmanager
def get_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row  # Enable dict-like access
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def generate_id() -> str:
    """Generate UUID for new records."""
    return str(uuid.uuid4())


def now_iso() -> str:
    """Current datetime in ISO format."""
    return datetime.now().isoformat()


def today_iso() -> str:
    """Current date in ISO format."""
    return date.today().isoformat()


# ============================================
# ATTENDANCE FUNCTIONS
# ============================================

def create_attendance(
    tenant_id: str,
    date_str: str,
    mentor_group_id: str,
    submitted_by_id: Optional[str] = None
) -> str:
    """Create attendance record. Returns attendance ID."""
    attendance_id = generate_id()
    
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO attendance (id, tenant_id, date, mentor_group_id, submitted_by_id, status)
            VALUES (?, ?, ?, ?, ?, 'Pending')
        """, (attendance_id, tenant_id, date_str, mentor_group_id, submitted_by_id))
        conn.commit()
    
    return attendance_id


def get_attendance(attendance_id: str) -> Optional[Dict]:
    """Get attendance record by ID."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM attendance WHERE id = ?", 
            (attendance_id,)
        ).fetchone()
        return dict(row) if row else None


def get_attendance_by_group_date(mentor_group_id: str, date_str: str) -> Optional[Dict]:
    """Get attendance for a mentor group on a specific date."""
    with get_connection() as conn:
        row = conn.execute("""
            SELECT * FROM attendance 
            WHERE mentor_group_id = ? AND date = ?
        """, (mentor_group_id, date_str)).fetchone()
        return dict(row) if row else None


def submit_attendance(attendance_id: str, submitted_by_id: Optional[str] = None) -> bool:
    """Mark attendance as submitted."""
    with get_connection() as conn:
        conn.execute("""
            UPDATE attendance 
            SET status = 'Submitted', 
                submitted_at = ?,
                submitted_by_id = COALESCE(?, submitted_by_id),
                updated_at = ?
            WHERE id = ?
        """, (now_iso(), submitted_by_id, now_iso(), attendance_id))
        conn.commit()
        return conn.total_changes > 0


def get_attendance_summary(tenant_id: str, date_str: str) -> List[Dict]:
    """Get all attendance records for a tenant on a date with entry counts."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT 
                a.*,
                COUNT(e.id) as total_learners,
                SUM(CASE WHEN e.status = 'Present' THEN 1 ELSE 0 END) as present_count,
                SUM(CASE WHEN e.status = 'Absent' THEN 1 ELSE 0 END) as absent_count,
                SUM(CASE WHEN e.status = 'Late' THEN 1 ELSE 0 END) as late_count,
                SUM(CASE WHEN e.status = 'Unmarked' THEN 1 ELSE 0 END) as unmarked_count
            FROM attendance a
            LEFT JOIN attendance_entry e ON a.id = e.attendance_id
            WHERE a.tenant_id = ? AND a.date = ?
            GROUP BY a.id
            ORDER BY a.created_at
        """, (tenant_id, date_str)).fetchall()
        return [dict(row) for row in rows]


# ============================================
# ATTENDANCE ENTRY FUNCTIONS
# ============================================

def create_attendance_entry(
    attendance_id: str,
    learner_id: str,
    status: str = 'Unmarked',
    notes: Optional[str] = None
) -> str:
    """Create attendance entry. Returns entry ID."""
    entry_id = generate_id()
    
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO attendance_entry (id, attendance_id, learner_id, status, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (entry_id, attendance_id, learner_id, status, notes))
        conn.commit()
    
    return entry_id


def bulk_create_entries(attendance_id: str, learner_ids: List[str]) -> int:
    """Create entries for multiple learners. Returns count created."""
    with get_connection() as conn:
        entries = [(generate_id(), attendance_id, lid, 'Unmarked') for lid in learner_ids]
        conn.executemany("""
            INSERT INTO attendance_entry (id, attendance_id, learner_id, status)
            VALUES (?, ?, ?, ?)
        """, entries)
        conn.commit()
        return len(entries)


def update_entry_status(entry_id: str, status: str, notes: Optional[str] = None) -> bool:
    """Update attendance entry status."""
    with get_connection() as conn:
        if notes is not None:
            conn.execute("""
                UPDATE attendance_entry 
                SET status = ?, notes = ?, updated_at = ?
                WHERE id = ?
            """, (status, notes, now_iso(), entry_id))
        else:
            conn.execute("""
                UPDATE attendance_entry 
                SET status = ?, updated_at = ?
                WHERE id = ?
            """, (status, now_iso(), entry_id))
        conn.commit()
        return conn.total_changes > 0


def get_entries_for_attendance(attendance_id: str) -> List[Dict]:
    """Get all entries for an attendance record."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM attendance_entry 
            WHERE attendance_id = ?
            ORDER BY created_at
        """, (attendance_id,)).fetchall()
        return [dict(row) for row in rows]


def get_entry_by_learner(attendance_id: str, learner_id: str) -> Optional[Dict]:
    """Get entry for a specific learner in an attendance record."""
    with get_connection() as conn:
        row = conn.execute("""
            SELECT * FROM attendance_entry 
            WHERE attendance_id = ? AND learner_id = ?
        """, (attendance_id, learner_id)).fetchone()
        return dict(row) if row else None


# ============================================
# LEARNER TRACKING FUNCTIONS
# ============================================

def update_learner_tracking(
    learner_id: str,
    tenant_id: str,
    status: str,
    attendance_date: str
) -> None:
    """Update learner's consecutive absent days tracking."""
    with get_connection() as conn:
        # Get current tracking
        row = conn.execute(
            "SELECT * FROM learner_absent_tracking WHERE learner_id = ?",
            (learner_id,)
        ).fetchone()
        
        if status == 'Absent':
            # Increment consecutive days
            if row:
                new_count = row['consecutive_absent_days'] + 1
                conn.execute("""
                    UPDATE learner_absent_tracking 
                    SET consecutive_absent_days = ?, last_status = ?, 
                        last_attendance_date = ?, updated_at = ?
                    WHERE learner_id = ?
                """, (new_count, status, attendance_date, now_iso(), learner_id))
            else:
                conn.execute("""
                    INSERT INTO learner_absent_tracking 
                    (learner_id, tenant_id, consecutive_absent_days, last_status, last_attendance_date)
                    VALUES (?, ?, 1, ?, ?)
                """, (learner_id, tenant_id, status, attendance_date))
        else:
            # Reset to 0 for Present/Late
            if row:
                conn.execute("""
                    UPDATE learner_absent_tracking 
                    SET consecutive_absent_days = 0, last_status = ?, 
                        last_attendance_date = ?, updated_at = ?
                    WHERE learner_id = ?
                """, (status, attendance_date, now_iso(), learner_id))
            else:
                conn.execute("""
                    INSERT INTO learner_absent_tracking 
                    (learner_id, tenant_id, consecutive_absent_days, last_status, last_attendance_date)
                    VALUES (?, ?, 0, ?, ?)
                """, (learner_id, tenant_id, status, attendance_date))
        
        conn.commit()


def get_learner_tracking(learner_id: str) -> Optional[Dict]:
    """Get tracking info for a learner."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM learner_absent_tracking WHERE learner_id = ?",
            (learner_id,)
        ).fetchone()
        return dict(row) if row else None


def get_high_absence_learners(tenant_id: str, min_days: int = 3) -> List[Dict]:
    """Get learners with consecutive absences >= threshold."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM learner_absent_tracking 
            WHERE tenant_id = ? AND consecutive_absent_days >= ?
            ORDER BY consecutive_absent_days DESC
        """, (tenant_id, min_days)).fetchall()
        return [dict(row) for row in rows]


# ============================================
# ABSENCE FUNCTIONS (Teacher)
# ============================================

def create_absence(
    tenant_id: str,
    staff_id: str,
    absence_date: str,
    absence_type: str,
    is_full_day: bool = True,
    start_period_id: Optional[str] = None,
    end_period_id: Optional[str] = None,
    reported_by_id: Optional[str] = None,
    reason: Optional[str] = None
) -> str:
    """Create teacher absence record. Returns absence ID."""
    absence_id = generate_id()
    
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO absence 
            (id, tenant_id, staff_id, absence_date, absence_type, is_full_day,
             start_period_id, end_period_id, reported_by_id, reported_at, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (absence_id, tenant_id, staff_id, absence_date, absence_type,
              1 if is_full_day else 0, start_period_id, end_period_id,
              reported_by_id, now_iso(), reason))
        conn.commit()
    
    return absence_id


def get_absences_by_date(tenant_id: str, date_str: str) -> List[Dict]:
    """Get all absences for a tenant on a date."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM absence 
            WHERE tenant_id = ? AND absence_date = ?
            ORDER BY created_at
        """, (tenant_id, date_str)).fetchall()
        return [dict(row) for row in rows]


def update_absence_status(absence_id: str, status: str) -> bool:
    """Update absence status."""
    with get_connection() as conn:
        conn.execute("""
            UPDATE absence SET status = ?, updated_at = ? WHERE id = ?
        """, (status, now_iso(), absence_id))
        conn.commit()
        return conn.total_changes > 0


# ============================================
# SUBSTITUTE REQUEST FUNCTIONS
# ============================================

def create_substitute_request(
    tenant_id: str,
    absence_id: str,
    period_id: str,
    class_group_id: Optional[str] = None,
    venue_id: Optional[str] = None
) -> str:
    """Create substitute request. Returns request ID."""
    request_id = generate_id()
    
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO substitute_request 
            (id, tenant_id, absence_id, period_id, class_group_id, venue_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (request_id, tenant_id, absence_id, period_id, class_group_id, venue_id))
        conn.commit()
    
    return request_id


def assign_substitute(request_id: str, substitute_id: str) -> bool:
    """Assign a substitute to a request."""
    with get_connection() as conn:
        conn.execute("""
            UPDATE substitute_request 
            SET substitute_id = ?, status = 'Assigned', assigned_at = ?, updated_at = ?
            WHERE id = ?
        """, (substitute_id, now_iso(), now_iso(), request_id))
        conn.commit()
        return conn.total_changes > 0


def confirm_substitute(request_id: str) -> bool:
    """Confirm substitute assignment."""
    with get_connection() as conn:
        conn.execute("""
            UPDATE substitute_request 
            SET status = 'Confirmed', confirmed_at = ?, updated_at = ?
            WHERE id = ?
        """, (now_iso(), now_iso(), request_id))
        conn.commit()
        return conn.total_changes > 0


def get_pending_requests(tenant_id: str) -> List[Dict]:
    """Get all pending substitute requests."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT sr.*, a.staff_id as absent_staff_id, a.absence_date
            FROM substitute_request sr
            JOIN absence a ON sr.absence_id = a.id
            WHERE sr.tenant_id = ? AND sr.status IN ('Pending', 'Assigned')
            ORDER BY a.absence_date, sr.created_at
        """, (tenant_id,)).fetchall()
        return [dict(row) for row in rows]


# ============================================
# DUTY ROSTER FUNCTIONS
# ============================================

def create_duty_roster(
    tenant_id: str,
    duty_date: str,
    zone_id: str,
    staff_id: str
) -> str:
    """Create duty roster entry. Returns roster ID."""
    roster_id = generate_id()
    
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO duty_roster (id, tenant_id, duty_date, zone_id, staff_id)
            VALUES (?, ?, ?, ?, ?)
        """, (roster_id, tenant_id, duty_date, zone_id, staff_id))
        conn.commit()
    
    return roster_id


def get_duty_roster_by_date(tenant_id: str, date_str: str) -> List[Dict]:
    """Get duty roster for a date."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM duty_roster 
            WHERE tenant_id = ? AND duty_date = ?
            ORDER BY zone_id
        """, (tenant_id, date_str)).fetchall()
        return [dict(row) for row in rows]


def get_staff_duties(staff_id: str, from_date: str, to_date: str) -> List[Dict]:
    """Get duties for a staff member in date range."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT * FROM duty_roster 
            WHERE staff_id = ? AND duty_date BETWEEN ? AND ?
            ORDER BY duty_date
        """, (staff_id, from_date, to_date)).fetchall()
        return [dict(row) for row in rows]


def update_duty_status(roster_id: str, status: str) -> bool:
    """Update duty roster status."""
    with get_connection() as conn:
        conn.execute("""
            UPDATE duty_roster SET status = ?, updated_at = ? WHERE id = ?
        """, (status, now_iso(), roster_id))
        conn.commit()
        return conn.total_changes > 0


def mark_reminder_sent(roster_id: str, reminder_type: str) -> bool:
    """Mark a reminder as sent. reminder_type: evening, morning, before"""
    column = f"reminder_{reminder_type}_sent"
    with get_connection() as conn:
        conn.execute(f"""
            UPDATE duty_roster SET {column} = 1, updated_at = ? WHERE id = ?
        """, (now_iso(), roster_id))
        conn.commit()
        return conn.total_changes > 0


# ============================================
# ADMIN / REPORTING FUNCTIONS
# ============================================

def get_absent_learners_today(tenant_id: str, date_str: Optional[str] = None) -> List[Dict]:
    """Get all absent learners for today (or specified date)."""
    if date_str is None:
        date_str = today_iso()
    
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT e.*, a.mentor_group_id, a.date
            FROM attendance_entry e
            JOIN attendance a ON e.attendance_id = a.id
            WHERE a.tenant_id = ? AND a.date = ? AND e.status = 'Absent'
            ORDER BY a.mentor_group_id, e.learner_id
        """, (tenant_id, date_str)).fetchall()
        return [dict(row) for row in rows]


def get_submission_stats(tenant_id: str, date_str: Optional[str] = None) -> Dict:
    """Get attendance submission statistics."""
    if date_str is None:
        date_str = today_iso()
    
    with get_connection() as conn:
        row = conn.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'Submitted' THEN 1 ELSE 0 END) as submitted,
                SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) as late
            FROM attendance
            WHERE tenant_id = ? AND date = ?
        """, (tenant_id, date_str)).fetchone()
        return dict(row) if row else {'total': 0, 'submitted': 0, 'pending': 0, 'late': 0}


# Initialize on import if database doesn't exist
if not get_db_path().exists():
    init_db()


# ============================================

def get_mentor_groups_sqlite(tenant_id: str = "MARAGON") -> list:
    """Get all mentor groups from SQLite."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, group_name, mentor_id, grade_id, venue_id
            FROM mentor_group WHERE tenant_id = ? ORDER BY group_name
        ''', (tenant_id,))
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_mentor_group_by_id_sqlite(group_id: str) -> dict:
    """Get single mentor group from SQLite."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, group_name, mentor_id, grade_id, venue_id FROM mentor_group WHERE id = ?', (group_id,))
        row = cursor.fetchone()
    return dict(row) if row else None


def get_learners_by_mentor_group_sqlite(mentor_group_id: str) -> list:
    """Get all learners in a mentor group from SQLite."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT l.id, l.first_name, l.surname, l.grade_id, l.mentor_group_id,
                   COALESCE(t.consecutive_absent_days, 0) as consecutive_absent_days
            FROM learner l
            LEFT JOIN learner_absent_tracking t ON l.id = t.learner_id
            WHERE l.mentor_group_id = ? AND l.is_active = 1
            ORDER BY l.surname, l.first_name
        ''', (mentor_group_id,))
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_staff_by_id_sqlite(staff_id: str) -> dict:
    """Get single staff member from SQLite."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, title, first_name, surname, display_name, email, staff_type FROM staff WHERE id = ?', (staff_id,))
        row = cursor.fetchone()
    return dict(row) if row else None


# ============================================
# PENDING ATTENDANCE (Cross-device sync)
# ============================================

def mark_learner_sqlite(mentor_group_id: str, learner_id: str, status: str, marked_by: str = None):
    """Mark a learner's attendance status in SQLite."""
    from datetime import datetime
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO pending_attendance
            (mentor_group_id, learner_id, status, marked_by, marked_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (mentor_group_id, learner_id, status, marked_by, datetime.now().isoformat()))
        conn.commit()


def get_pending_marks_sqlite(mentor_group_id: str) -> dict:
    """Get all pending marks for a mentor group. Returns {learner_id: status}."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT learner_id, status FROM pending_attendance WHERE mentor_group_id = ?
        ''', (mentor_group_id,))
        rows = cursor.fetchall()
    return {row['learner_id']: row['status'] for row in rows}


def get_pending_stats_sqlite(mentor_group_id: str) -> dict:
    """Get attendance stats for a mentor group."""
    with get_connection() as conn:
        cursor = conn.cursor()
        # Get total learners
        cursor.execute('SELECT COUNT(*) as total FROM learner WHERE mentor_group_id = ? AND is_active = 1', (mentor_group_id,))
        total = cursor.fetchone()['total']
        
        # Get counts by status
        cursor.execute('''
            SELECT status, COUNT(*) as count FROM pending_attendance 
            WHERE mentor_group_id = ? GROUP BY status
        ''', (mentor_group_id,))
        counts = {row['status']: row['count'] for row in cursor.fetchall()}
    
    present = counts.get('Present', 0)
    absent = counts.get('Absent', 0)
    late = counts.get('Late', 0)
    unmarked = total - present - absent - late
    
    return {'present': present, 'absent': absent, 'late': late, 'unmarked': unmarked}


def clear_pending_attendance_sqlite(mentor_group_id: str):
    """Clear pending attendance after submission."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM pending_attendance WHERE mentor_group_id = ?', (mentor_group_id,))
        conn.commit()



def get_mentor_group_with_mentor_sqlite(group_id: str) -> dict:
    """Get mentor group with mentor teacher name."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT mg.id, mg.group_name, mg.mentor_id, mg.grade_id, mg.venue_id,
                   s.display_name as mentor_name
            FROM mentor_group mg
            LEFT JOIN staff s ON mg.mentor_id = s.id
            WHERE mg.id = ?
        ''', (group_id,))
        row = cursor.fetchone()
    return dict(row) if row else None


def create_attendance(tenant_id: str, attendance_date: str, mentor_group_id: str, submitted_by_id: str, status: str) -> str:
    """Create attendance record and return its ID."""
    import uuid
    from datetime import datetime
    
    attendance_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO attendance (id, tenant_id, date, mentor_group_id, submitted_by_id, submitted_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (attendance_id, tenant_id, attendance_date, mentor_group_id, submitted_by_id, now, status))
        conn.commit()
    
    return attendance_id


def create_attendance_entry(attendance_id: str, learner_id: str, status: str, notes: str = None):
    """Create attendance entry for a learner."""
    import uuid
    
    entry_id = str(uuid.uuid4())
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO attendance_entry (id, attendance_id, learner_id, status, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (entry_id, attendance_id, learner_id, status, notes))
        conn.commit()
    
    return entry_id

def update_learner_absent_tracking(learner_id: str, increment: bool = True, tenant_id: str = "MARAGON"):
    """Update consecutive absent days for a learner."""
    from datetime import datetime, date
    
    now = datetime.now().isoformat()
    today = date.today().isoformat()
    status = "Absent" if increment else "Present"
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        if increment:
            cursor.execute("""
                INSERT INTO learner_absent_tracking (learner_id, tenant_id, consecutive_absent_days, last_status, last_attendance_date, updated_at)
                VALUES (?, ?, 1, ?, ?, ?)
                ON CONFLICT(learner_id) DO UPDATE SET
                    consecutive_absent_days = consecutive_absent_days + 1,
                    last_status = ?,
                    last_attendance_date = ?,
                    updated_at = ?
            """, (learner_id, tenant_id, status, today, now, status, today, now))
        else:
            cursor.execute("""
                INSERT INTO learner_absent_tracking (learner_id, tenant_id, consecutive_absent_days, last_status, last_attendance_date, updated_at)
                VALUES (?, ?, 0, ?, ?, ?)
                ON CONFLICT(learner_id) DO UPDATE SET
                    consecutive_absent_days = 0,
                    last_status = ?,
                    last_attendance_date = ?,
                    updated_at = ?
            """, (learner_id, tenant_id, status, today, now, status, today, now))
        
        conn.commit()



def get_attendance_for_today(mentor_group_id: str, attendance_date: str) -> dict:
    """Check if attendance already submitted for this group today."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, submitted_at, status, stasy_captured
            FROM attendance
            WHERE mentor_group_id = ? AND date = ?
            ORDER BY submitted_at DESC
            LIMIT 1
        ''', (mentor_group_id, attendance_date))
        row = cursor.fetchone()
    return dict(row) if row else None


def get_attendance_entries(attendance_id: str) -> dict:
    """Get all entries for an attendance record as {learner_id: status}."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT learner_id, status
            FROM attendance_entry
            WHERE attendance_id = ?
        ''', (attendance_id,))
        return {row['learner_id']: row['status'] for row in cursor.fetchall()}


def update_attendance_entry(attendance_id: str, learner_id: str, status: str):
    """Update a single attendance entry."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE attendance_entry
            SET status = ?
            WHERE attendance_id = ? AND learner_id = ?
        ''', (status, attendance_id, learner_id))
        conn.commit()


def update_attendance_submitted(attendance_id: str):
    """Update submitted timestamp on re-submit."""
    from datetime import datetime
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE attendance
            SET submitted_at = ?, status = 'Submitted'
            WHERE id = ?
        ''', (datetime.now().isoformat(), attendance_id))
        conn.commit()


def mark_stasy_captured(attendance_id: str, captured_by: str = None):
    """Mark attendance as captured in STASY."""
    from datetime import datetime
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE attendance
            SET stasy_captured = 1, stasy_captured_at = ?, stasy_captured_by = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), captured_by, attendance_id))
        conn.commit()


def get_attendance_with_entries(attendance_id: str) -> list:
    """Get attendance entries with learner details for admin view."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ae.id as entry_id, ae.learner_id, ae.status, ae.notes,
                   l.first_name, l.surname
            FROM attendance_entry ae
            JOIN learner l ON ae.learner_id = l.id
            WHERE ae.attendance_id = ?
            ORDER BY l.surname, l.first_name
        ''', (attendance_id,))
        return [dict(row) for row in cursor.fetchall()]
