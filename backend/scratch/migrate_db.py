import sys
from pathlib import Path

# Add backend directory to Python path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))
sys.path.insert(0, str(backend_dir.parent))

from backend.database import engine
from sqlalchemy import text

def run_migration():
    print("Running migration to add hash_version to audit_logs...")
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS hash_version INTEGER DEFAULT 2;"))
    print("Migration completed successfully!")

if __name__ == '__main__':
    run_migration()
