"""
FlexFlow Migrations Runner
Executes all database migrations in the correct order.
"""
import sys
import os
import io
from pathlib import Path

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.database import engine, Base
from backend.models import *  # Load all models to register them with Base

# Import all migrations
from backend.migrations.add_staging_fields import upgrade as upgrade_staging_fields
from backend.migrations.add_costs_and_metadata import run_migration as run_costs_metadata
from backend.migrations.add_credit_status_constraints import run_migration as run_credit_constraints
from backend.migrations.add_financial_fields import upgrade as upgrade_financial_fields
from backend.migrations.add_financial_value_fields import run_migration as run_financial_value
from backend.migrations.add_global_config_and_enums import run_migration as run_global_config
from backend.migrations.add_partition_feature import run_migration as run_partition_feature
from backend.migrations.add_support_tickets import run_migration as run_support_tickets
from backend.migrations.fix_status_constraints import run_migration as run_status_constraints

def run_all_migrations():
    print("=" * 60)
    print("🚀 RUNNING ALL DATABASE MIGRATIONS")
    print("=" * 60)
    
    # 1. Base table creation
    print("\n📦 Step 1: Initializing base tables...")
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ Base tables initialized successfully.")
    except Exception as e:
        print(f"❌ Error creating base tables: {e}")
        sys.exit(1)
        
    # 2. Sequential migrations
    migrations = [
        ("Add Staging Fields", upgrade_staging_fields),
        ("Add Costs and Metadata", run_costs_metadata),
        ("Add Credit Status Constraints", run_credit_constraints),
        ("Add Financial Fields", upgrade_financial_fields),
        ("Add Financial Value Fields", run_financial_value),
        ("Add Global Config & Enums", run_global_config),
        ("Add Partition Feature", run_partition_feature),
        ("Add Support Tickets", run_support_tickets),
        ("Fix Status Constraints", run_status_constraints),
    ]
    
    success_count = 0
    for name, migration_func in migrations:
        print(f"\n🔧 Running migration: {name}...")
        try:
            # Some functions return a boolean for success
            res = migration_func()
            if res is False:
                print(f"❌ Migration failed (returned False): {name}")
            else:
                print(f"✅ Migration successful: {name}")
                success_count += 1
        except Exception as e:
            print(f"⚠️  Migration warning/error on '{name}': {e}")
            print("   Continuing with next migration...")
            
    print("\n" + "=" * 60)
    print(f"🎉 MIGRATIONS RUN COMPLETE ({success_count}/{len(migrations)} successful)")
    print("=" * 60)

if __name__ == "__main__":
    run_all_migrations()
