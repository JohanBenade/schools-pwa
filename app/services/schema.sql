-- SchoolOps SQLite Schema
-- Transactional tables (high-frequency writes)
-- Reference data remains in Notion (S_Staff, S_Learner, S_Mentor_Group, etc.)

-- Enable foreign keys
PRAGMA foreign_keys = ON;

-- ============================================
-- ATTENDANCE MODULE
-- ============================================

CREATE TABLE IF NOT EXISTS attendance (
    id TEXT PRIMARY KEY,                    -- UUID generated in Python
    tenant_id TEXT NOT NULL,                -- Notion tenant page ID
    date TEXT NOT NULL,                     -- ISO date: YYYY-MM-DD
    mentor_group_id TEXT NOT NULL,          -- Notion mentor_group page ID
    submitted_by_id TEXT,                   -- Notion staff page ID (nullable until auth)
    submitted_at TEXT,                      -- ISO datetime
    status TEXT NOT NULL DEFAULT 'Pending', -- Pending, Submitted, Late
    stasy_captured INTEGER DEFAULT 0,       -- Has been captured to STASY
    stasy_captured_at TEXT,                 -- When captured
    stasy_captured_by TEXT,                 -- Who captured
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);
CREATE INDEX IF NOT EXISTS idx_attendance_mentor_group ON attendance(mentor_group_id);
CREATE INDEX IF NOT EXISTS idx_attendance_tenant_date ON attendance(tenant_id, date);

CREATE TABLE IF NOT EXISTS attendance_entry (
    id TEXT PRIMARY KEY,                    -- UUID generated in Python
    attendance_id TEXT NOT NULL,            -- FK to attendance
    learner_id TEXT NOT NULL,               -- Notion learner page ID
    status TEXT NOT NULL DEFAULT 'Unmarked', -- Unmarked, Present, Absent, Late, Left_Early
    notes TEXT,
    stasy_captured INTEGER DEFAULT 0,       -- Has been captured to STASY
    stasy_captured_at TEXT,                 -- When captured
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (attendance_id) REFERENCES attendance(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entry_attendance ON attendance_entry(attendance_id);
CREATE INDEX IF NOT EXISTS idx_entry_learner ON attendance_entry(learner_id);

-- ============================================
-- ABSENCE MODULE (Teacher absences)
-- ============================================

CREATE TABLE IF NOT EXISTS absence (
    id TEXT PRIMARY KEY,                    -- UUID
    tenant_id TEXT NOT NULL,
    staff_id TEXT NOT NULL,                 -- Notion staff page ID
    absence_date TEXT NOT NULL,             -- ISO date
    absence_type TEXT NOT NULL,             -- Sick, Personal, School_Duty, Training, Other
    start_period_id TEXT,                   -- Notion period page ID
    end_period_id TEXT,                     -- Notion period page ID
    is_full_day INTEGER NOT NULL DEFAULT 1, -- 0=false, 1=true
    reported_by_id TEXT,                    -- Notion staff page ID
    reported_at TEXT,                       -- ISO datetime
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'Reported', -- Reported, Covered, Escalated
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_absence_date ON absence(absence_date);
CREATE INDEX IF NOT EXISTS idx_absence_staff ON absence(staff_id);
CREATE INDEX IF NOT EXISTS idx_absence_tenant_date ON absence(tenant_id, absence_date);

-- ============================================
-- SUBSTITUTE MODULE
-- ============================================

CREATE TABLE IF NOT EXISTS substitute_request (
    id TEXT PRIMARY KEY,                    -- UUID
    tenant_id TEXT NOT NULL,
    absence_id TEXT NOT NULL,               -- FK to absence
    period_id TEXT,                         -- Notion period page ID (NULL for mentor duty)
    class_group_id TEXT,                    -- Notion class_group page ID
    venue_id TEXT,                          -- Notion venue page ID
    substitute_id TEXT,                     -- Notion staff page ID (assigned sub)
    status TEXT NOT NULL DEFAULT 'Pending', -- Pending, Assigned, Confirmed, Declined, Escalated
    assigned_at TEXT,                       -- ISO datetime
    confirmed_at TEXT,                      -- ISO datetime
    is_mentor_duty INTEGER DEFAULT 0,       -- 1 if this is mentor roll call coverage
    mentor_group_id TEXT,                   -- FK to mentor_group (for mentor duty)
    subject TEXT,                           -- Subject name for display
    class_name TEXT,                        -- Class name for display
    venue_name TEXT,                        -- Venue name for display
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (absence_id) REFERENCES absence(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_subreq_absence ON substitute_request(absence_id);
CREATE INDEX IF NOT EXISTS idx_subreq_substitute ON substitute_request(substitute_id);
CREATE INDEX IF NOT EXISTS idx_subreq_status ON substitute_request(status);

-- ============================================
-- TERRAIN DUTY MODULE
-- ============================================

CREATE TABLE IF NOT EXISTS duty_roster (
    id TEXT PRIMARY KEY,                    -- UUID
    tenant_id TEXT NOT NULL,
    duty_date TEXT NOT NULL,                -- ISO date
    zone_id TEXT NOT NULL,                  -- Notion zone page ID
    staff_id TEXT NOT NULL,                 -- Notion staff page ID
    status TEXT NOT NULL DEFAULT 'Scheduled', -- Scheduled, Confirmed, Completed, Missed, Swapped
    confirmed_at TEXT,                      -- ISO datetime
    reminder_evening_sent INTEGER NOT NULL DEFAULT 0,
    reminder_morning_sent INTEGER NOT NULL DEFAULT 0,
    reminder_before_sent INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_duty_date ON duty_roster(duty_date);
CREATE INDEX IF NOT EXISTS idx_duty_staff ON duty_roster(staff_id);
CREATE INDEX IF NOT EXISTS idx_duty_tenant_date ON duty_roster(tenant_id, duty_date);

-- ============================================
-- LEARNER TRACKING (denormalized for performance)
-- Updated when attendance submitted
-- ============================================

CREATE TABLE IF NOT EXISTS learner_absent_tracking (
    learner_id TEXT PRIMARY KEY,            -- Notion learner page ID
    tenant_id TEXT NOT NULL,
    consecutive_absent_days INTEGER NOT NULL DEFAULT 0,
    last_status TEXT,                       -- Last attendance status
    last_attendance_date TEXT,              -- ISO date
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tracking_tenant ON learner_absent_tracking(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tracking_consecutive ON learner_absent_tracking(consecutive_absent_days DESC);

-- ============================================
-- SCHEMA VERSION (for future migrations)
-- ============================================

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT
);

INSERT OR IGNORE INTO schema_version (version, description) 
VALUES (1, 'Initial schema - attendance, absence, substitute, duty_roster');

-- ============================================
-- REFERENCE DATA (synced from Notion)
-- ============================================

CREATE TABLE IF NOT EXISTS staff (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    title TEXT,
    first_name TEXT,
    surname TEXT,
    display_name TEXT,
    email TEXT,
    staff_type TEXT,
    can_substitute INTEGER DEFAULT 0,
    can_do_duty INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    synced_at TEXT
);

CREATE TABLE IF NOT EXISTS learner (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    first_name TEXT,
    surname TEXT,
    grade_id TEXT,
    mentor_group_id TEXT,
    house_id TEXT,
    is_active INTEGER DEFAULT 1,
    synced_at TEXT
);

CREATE TABLE IF NOT EXISTS mentor_group (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    group_name TEXT,
    mentor_id TEXT,
    grade_id TEXT,
    venue_id TEXT,
    synced_at TEXT
);

CREATE TABLE IF NOT EXISTS grade (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    grade_name TEXT,
    grade_code TEXT,
    grade_number INTEGER,
    sort_order INTEGER,
    synced_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_learner_mentor_group ON learner(mentor_group_id);
CREATE INDEX IF NOT EXISTS idx_learner_tenant ON learner(tenant_id);
CREATE INDEX IF NOT EXISTS idx_mentor_group_tenant ON mentor_group(tenant_id);
CREATE INDEX IF NOT EXISTS idx_staff_tenant ON staff(tenant_id);

-- ============================================
-- PENDING ATTENDANCE (cross-device sync)
-- ============================================

CREATE TABLE IF NOT EXISTS pending_attendance (
    mentor_group_id TEXT NOT NULL,
    learner_id TEXT NOT NULL,
    date TEXT NOT NULL,
    status TEXT NOT NULL,
    marked_by TEXT,
    marked_at TEXT,
    PRIMARY KEY (mentor_group_id, learner_id, date)
);

CREATE INDEX IF NOT EXISTS idx_pending_mentor_group ON pending_attendance(mentor_group_id);
CREATE INDEX IF NOT EXISTS idx_pending_date ON pending_attendance(date);
-- ============================================
-- VENUE MODULE
-- ============================================

CREATE TABLE IF NOT EXISTS venue (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    venue_code TEXT NOT NULL,
    venue_name TEXT,
    venue_type TEXT,            -- classroom, office, terrain, facility
    block TEXT,                 -- A_Ground, A_First, A_Admin, B, C, D, Outdoor
    sort_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_venue_tenant ON venue(tenant_id);
CREATE INDEX IF NOT EXISTS idx_venue_block ON venue(block);

-- Staff to venue assignment (home classroom)
CREATE TABLE IF NOT EXISTS staff_venue (
    staff_id TEXT PRIMARY KEY,
    venue_id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (venue_id) REFERENCES venue(id)
);

-- ============================================
-- EMERGENCY MODULE
-- ============================================

CREATE TABLE IF NOT EXISTS emergency_alert (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    alert_type TEXT NOT NULL,       -- Medical, Security, Fire, General
    venue_id TEXT,
    location_display TEXT,          -- Human readable: "A104 - Ms Nadia"
    triggered_by_id TEXT NOT NULL,
    triggered_at TEXT NOT NULL,
    status TEXT DEFAULT 'Active',   -- Active, Resolved
    resolved_at TEXT,
    resolved_by_id TEXT,
    resolution_type TEXT,           -- AllClear, FalseAlarm, Escalated
    resolution_notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_alert_tenant ON emergency_alert(tenant_id);
CREATE INDEX IF NOT EXISTS idx_alert_status ON emergency_alert(status);
CREATE INDEX IF NOT EXISTS idx_alert_triggered ON emergency_alert(triggered_at DESC);

CREATE TABLE IF NOT EXISTS emergency_response (
    id TEXT PRIMARY KEY,
    alert_id TEXT NOT NULL,
    responder_id TEXT NOT NULL,
    responded_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (alert_id) REFERENCES emergency_alert(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_response_alert ON emergency_response(alert_id);

-- ============================================
-- USER SESSION MODULE (Magic Links)
-- ============================================

CREATE TABLE IF NOT EXISTS user_session (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    staff_id TEXT NOT NULL,
    magic_code TEXT UNIQUE NOT NULL,    -- Short code for URL: nadia, pierre, admin
    display_name TEXT,
    role TEXT DEFAULT 'teacher',        -- teacher, principal, deputy, grade_head, admin
    can_resolve INTEGER DEFAULT 0,      -- Can resolve emergency alerts
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_session_magic ON user_session(magic_code);
CREATE INDEX IF NOT EXISTS idx_session_staff ON user_session(staff_id);

-- ============================================
-- PUSH SUBSCRIPTION MODULE
-- ============================================

CREATE TABLE IF NOT EXISTS push_subscription (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    staff_id TEXT,                      -- Nullable until linked to user
    endpoint TEXT NOT NULL UNIQUE,      -- Push endpoint URL
    p256dh TEXT NOT NULL,               -- Public key
    auth TEXT NOT NULL,                 -- Auth secret
    user_agent TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    last_used_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_push_tenant ON push_subscription(tenant_id);
CREATE INDEX IF NOT EXISTS idx_push_staff ON push_subscription(staff_id);

-- ============================================
-- UPDATE SCHEMA VERSION
-- ============================================

INSERT OR IGNORE INTO schema_version (version, description) 
VALUES (2, 'Emergency alerts, venues, user sessions, push subscriptions');

-- ============================================
-- SUBSTITUTE ALLOCATION MODULE (v3)
-- ============================================

-- Period definitions (Period 1-8 + breaks)
CREATE TABLE IF NOT EXISTS period (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    period_number INTEGER NOT NULL,         -- 1, 2, 3... 8 (0 for breaks)
    period_name TEXT NOT NULL,              -- "Period 1", "Break 1"
    start_time TEXT NOT NULL,               -- "07:30"
    end_time TEXT NOT NULL,                 -- "08:15"
    is_teaching INTEGER NOT NULL DEFAULT 1, -- 1=teaching period, 0=break
    sort_order INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_period_tenant ON period(tenant_id);
CREATE INDEX IF NOT EXISTS idx_period_sort ON period(tenant_id, sort_order);

-- Timetable slots: who teaches what, when, where
CREATE TABLE IF NOT EXISTS timetable_slot (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    staff_id TEXT NOT NULL,                 -- FK to staff
    cycle_day INTEGER NOT NULL,             -- 1-7 (7-day cycle)
    period_id TEXT NOT NULL,                -- FK to period
    class_name TEXT,                        -- "Grade 10A", "11 Eng HL"
    subject TEXT,                           -- "English", "Mathematics"
    venue_id TEXT,                          -- FK to venue
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (staff_id) REFERENCES staff(id),
    FOREIGN KEY (period_id) REFERENCES period(id),
    FOREIGN KEY (venue_id) REFERENCES venue(id)
);

CREATE INDEX IF NOT EXISTS idx_timetable_staff ON timetable_slot(staff_id);
CREATE INDEX IF NOT EXISTS idx_timetable_day_period ON timetable_slot(tenant_id, cycle_day, period_id);
CREATE INDEX IF NOT EXISTS idx_timetable_tenant ON timetable_slot(tenant_id);

-- Substitute configuration per tenant
CREATE TABLE IF NOT EXISTS substitute_config (
    tenant_id TEXT PRIMARY KEY,
    pointer_surname TEXT DEFAULT 'A',       -- Current position in A-Z rotation
    pointer_updated_at TEXT,                -- When pointer last moved
    cycle_start_date TEXT,                  -- First day of cycle: "2026-01-15"
    cycle_length INTEGER DEFAULT 7,         -- 7-day cycle
    quiet_hours_start TEXT DEFAULT '21:00', -- Don't send push after this
    quiet_hours_end TEXT DEFAULT '06:00',   -- Resume push after this
    decline_cutoff_minutes INTEGER DEFAULT 15, -- Can't decline within X min of period
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Substitute audit log (for Mission Control timeline)
CREATE TABLE IF NOT EXISTS substitute_log (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    absence_id TEXT NOT NULL,               -- FK to absence
    substitute_request_id TEXT,             -- FK to substitute_request (nullable)
    event_type TEXT NOT NULL,               -- See event types below
    staff_id TEXT,                          -- Who this event concerns (if applicable)
    details TEXT,                           -- JSON with additional context
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (absence_id) REFERENCES absence(id) ON DELETE CASCADE
);

-- Event types:
-- 'absence_reported'    - Sick note received
-- 'processing_started'  - System began allocation
-- 'allocated'           - Sub assigned to period
-- 'push_sent'           - Notification sent
-- 'push_queued'         - Notification queued (quiet hours)
-- 'no_cover'            - No substitute available
-- 'declined'            - Sub declined assignment
-- 'reassigned'          - New sub assigned after decline
-- 'confirmed'           - Sub confirmed assignment
-- 'processing_complete' - All periods processed
-- 'absence_cancelled'   - Sick note cancelled
-- 'cover_cancelled'     - Coverage cancelled due to absence cancellation

CREATE INDEX IF NOT EXISTS idx_sublog_absence ON substitute_log(absence_id);
CREATE INDEX IF NOT EXISTS idx_sublog_tenant_time ON substitute_log(tenant_id, created_at DESC);

-- ============================================
-- UPDATE SCHEMA VERSION
-- ============================================

INSERT OR IGNORE INTO schema_version (version, description) 
VALUES (3, 'Substitute allocation - periods, timetable, config, audit log');

-- ============================================
-- MIGRATION 004: Decline + Multi-day (Jan 2026)
-- ============================================

-- Absence: multi-day support
-- absence.end_date TEXT               -- Last day out (NULL = single day, same as start)
-- absence.is_open_ended INTEGER       -- 1 = "until further notice"
-- absence.returned_early INTEGER      -- 1 = came back before end_date
-- absence.returned_at TEXT            -- When they reported return
-- absence.return_reported_by_id TEXT  -- Who reported (self or admin)

-- Substitute request: decline + cancel tracking
-- substitute_request.declined_at TEXT
-- substitute_request.declined_by_id TEXT
-- substitute_request.decline_reason TEXT
-- substitute_request.cancelled_at TEXT
-- substitute_request.cancel_reason TEXT   -- 'early_return', 'absence_cancelled'
-- substitute_request.request_date TEXT    -- Which date this sub request is for

INSERT OR IGNORE INTO schema_version (version, description) 
VALUES (4, 'Decline flow + Multi-day absence support');

-- ============================================
-- MIGRATION 005: Terrain Duty + My Daily Schedule (Jan 2026)
-- ============================================

CREATE TABLE IF NOT EXISTS terrain_area (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    area_code TEXT NOT NULL,
    area_name TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_terrain_area_tenant ON terrain_area(tenant_id);
CREATE INDEX IF NOT EXISTS idx_terrain_area_sort ON terrain_area(tenant_id, sort_order);

CREATE TABLE IF NOT EXISTS school_calendar (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    date TEXT NOT NULL,
    cycle_day INTEGER,
    day_type TEXT NOT NULL,
    day_name TEXT,
    weekday TEXT NOT NULL,
    bell_schedule TEXT NOT NULL,
    is_school_day INTEGER DEFAULT 1,
    term INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(tenant_id, date)
);

CREATE INDEX IF NOT EXISTS idx_school_calendar_tenant_date ON school_calendar(tenant_id, date);
CREATE INDEX IF NOT EXISTS idx_school_calendar_school_day ON school_calendar(tenant_id, is_school_day, date);

CREATE TABLE IF NOT EXISTS bell_schedule (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    schedule_type TEXT NOT NULL,
    slot_type TEXT NOT NULL,
    slot_number INTEGER,
    slot_name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    is_teaching INTEGER DEFAULT 0,
    is_break INTEGER DEFAULT 0,
    sort_order INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_bell_schedule_tenant_type ON bell_schedule(tenant_id, schedule_type);
CREATE INDEX IF NOT EXISTS idx_bell_schedule_breaks ON bell_schedule(tenant_id, is_break);

CREATE TABLE IF NOT EXISTS teacher_meeting (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    staff_id TEXT NOT NULL,
    meeting_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT,
    title TEXT NOT NULL,
    meeting_type TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_teacher_meeting_staff ON teacher_meeting(staff_id);
CREATE INDEX IF NOT EXISTS idx_teacher_meeting_date ON teacher_meeting(tenant_id, meeting_date);

CREATE TABLE IF NOT EXISTS terrain_config (
    tenant_id TEXT PRIMARY KEY,
    pointer_index INTEGER DEFAULT 0,
    pointer_updated_at TEXT,
    morning_duty_time TEXT DEFAULT '07:15',
    reminder_evening_time TEXT DEFAULT '18:00',
    reminder_morning_time TEXT DEFAULT '06:30',
    reminder_before_minutes INTEGER DEFAULT 15,
    days_to_generate INTEGER DEFAULT 5,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT OR IGNORE INTO schema_version (version, description) 
VALUES (5, 'Terrain duty + My Daily Schedule - areas, calendar, bell schedules, meetings, config');
