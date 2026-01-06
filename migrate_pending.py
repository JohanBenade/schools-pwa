"""Migration: Add date column to pending_attendance"""
import sqlite3
import os

DB_PATH = os.environ.get('DATABASE_PATH', 'app/data/schoolops.db')

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if date column exists
    cursor.execute("PRAGMA table_info(pending_attendance)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'date' not in columns:
        print("Adding date column to pending_attendance...")
        # Drop and recreate table (SQLite doesn't support adding to PK)
        cursor.execute("DROP TABLE IF EXISTS pending_attendance")
        cursor.execute('''
            CREATE TABLE pending_attendance (
                mentor_group_id TEXT NOT NULL,
                learner_id TEXT NOT NULL,
                date TEXT NOT NULL,
                status TEXT NOT NULL,
                marked_by TEXT,
                marked_at TEXT,
                PRIMARY KEY (mentor_group_id, learner_id, date)
            )
        ''')
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_mentor_group ON pending_attendance(mentor_group_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pending_date ON pending_attendance(date)")
        conn.commit()
        print("SUCCESS: Migration complete")
    else:
        print("SKIP: date column already exists")
    
    conn.close()

if __name__ == '__main__':
    migrate()
