"""
Migration 004: Decline flow + Multi-day absence support
SchoolOps | January 2026
"""

def apply(cursor):
    """Apply migration - adds columns for decline and multi-day absence."""
    
    migrations = [
        # Absence table: multi-day support
        ("ALTER TABLE absence ADD COLUMN end_date TEXT", "absence.end_date"),
        ("ALTER TABLE absence ADD COLUMN is_open_ended INTEGER DEFAULT 0", "absence.is_open_ended"),
        ("ALTER TABLE absence ADD COLUMN returned_early INTEGER DEFAULT 0", "absence.returned_early"),
        ("ALTER TABLE absence ADD COLUMN returned_at TEXT", "absence.returned_at"),
        ("ALTER TABLE absence ADD COLUMN return_reported_by_id TEXT", "absence.return_reported_by_id"),
        
        # Substitute request: decline tracking
        ("ALTER TABLE substitute_request ADD COLUMN declined_at TEXT", "substitute_request.declined_at"),
        ("ALTER TABLE substitute_request ADD COLUMN declined_by_id TEXT", "substitute_request.declined_by_id"),
        ("ALTER TABLE substitute_request ADD COLUMN decline_reason TEXT", "substitute_request.decline_reason"),
        
        # Substitute request: cancellation tracking (early return)
        ("ALTER TABLE substitute_request ADD COLUMN cancelled_at TEXT", "substitute_request.cancelled_at"),
        ("ALTER TABLE substitute_request ADD COLUMN cancel_reason TEXT", "substitute_request.cancel_reason"),
        
        # Substitute request: which date this request is for (multi-day)
        ("ALTER TABLE substitute_request ADD COLUMN request_date TEXT", "substitute_request.request_date"),
        
        # Config: 30-min decline cutoff
        ("UPDATE substitute_config SET decline_cutoff_minutes = 30 WHERE tenant_id = 'MARAGON'", "config update"),
        
        # Indexes
        ("CREATE INDEX IF NOT EXISTS idx_subreq_date ON substitute_request(request_date)", "idx_subreq_date"),
        ("CREATE INDEX IF NOT EXISTS idx_absence_dates ON absence(absence_date, end_date)", "idx_absence_dates"),
    ]
    
    results = []
    for sql, name in migrations:
        try:
            cursor.execute(sql)
            results.append(f"✓ {name}")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                results.append(f"⏭ {name} (exists)")
            else:
                results.append(f"✗ {name}: {e}")
    
    return results
