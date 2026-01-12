"""Migrations package"""

def run_on_startup():
    """Run pending migrations - called from app factory."""
    try:
        from app.services.run_migrations import run_migrations
        run_migrations()
    except Exception as e:
        print(f"Migration warning: {e}")
