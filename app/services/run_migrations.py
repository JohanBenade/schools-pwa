"""
Migration runner - executes pending migrations on app startup.
"""

from app.services.db import get_connection

MIGRATIONS = [
    (4, "004_decline_multiday", "Decline flow + Multi-day absence support"),
    (10, "010_terrain_enhancements", "Terrain duty enhancements - Homework venue, decline tracking"),
]

def run_migrations():
    """Run all pending migrations."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Get current version
        cursor.execute("SELECT MAX(version) FROM schema_version")
        row = cursor.fetchone()
        current_version = row[0] if row and row[0] else 0
        
        for version, module_name, description in MIGRATIONS:
            if version > current_version:
                print(f"\n🔄 Running migration {version}: {description}")
                
                # Import and run migration
                module = __import__(f"app.services.migrations.{module_name}", fromlist=["apply"])
                results = module.apply(cursor)
                
                for r in results:
                    print(f"   {r}")
                
                # Record migration
                cursor.execute(
                    "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                    (version, description)
                )
                conn.commit()
                print(f"✅ Migration {version} complete")
        
        if current_version >= MIGRATIONS[-1][0]:
            print("📦 Database schema up to date")

if __name__ == "__main__":
    run_migrations()
