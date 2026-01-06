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
    period_id TEXT NOT NULL,                -- Notion period page ID
    class_group_id TEXT,                    -- Notion class_group page ID
    venue_id TEXT,                          -- Notion venue page ID
    substitute_id TEXT,                     -- Notion staff page ID (assigned sub)
    status TEXT NOT NULL DEFAULT 'Pending', -- Pending, Assigned, Confirmed, Declined, Escalated
    assigned_at TEXT,                       -- ISO datetime
    confirmed_at TEXT,                      -- ISO datetime
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
