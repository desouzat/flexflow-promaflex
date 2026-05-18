"""
Migration: Fix Status Constraints
Adds missing statuses to check_po_status_macro constraint.

CRITICAL FIX: Adds IN_PROGRESS, AUDIT_PENDING, and ensures all statuses are included.

Run with: python backend/migrations/fix_status_constraints.py
"""

import os
import sys
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

def get_timestamp():
    """Get formatted timestamp for logging"""
    return datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")

def run_migration():
    """
    Update the check_po_status_macro constraint to include all valid statuses.
    """
    print(f"{get_timestamp()} ========================================")
    print(f"{get_timestamp()} MIGRATION: Fix Status Constraints")
    print(f"{get_timestamp()} ========================================\n")
    
    # Get database URL from environment
    from dotenv import load_dotenv
    load_dotenv()
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print(f"{get_timestamp()} [ERROR] DATABASE_URL not found in environment")
        return False
    
    print(f"{get_timestamp()} [INFO] Connecting to database...")
    
    try:
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            print(f"{get_timestamp()} [INFO] Connected successfully")
            
            # Start transaction
            trans = conn.begin()
            
            try:
                # Step 1: Drop existing constraint
                print(f"{get_timestamp()} [STEP 1] Dropping existing check_po_status_macro constraint...")
                conn.execute(text("""
                    ALTER TABLE purchase_orders
                    DROP CONSTRAINT IF EXISTS check_po_status_macro;
                """))
                print(f"{get_timestamp()} [SUCCESS] Constraint dropped")
                
                # Step 2: Add new constraint with ALL statuses
                print(f"{get_timestamp()} [STEP 2] Adding new constraint with all statuses...")
                print(f"{get_timestamp()} [INFO] Including statuses:")
                statuses = [
                    'DRAFT',
                    'SUBMITTED',
                    'APPROVED',
                    'IN_PROGRESS',
                    'WAITING_DISPATCH',
                    'WAITING_COMMERCIAL_PARTITION',
                    'AUDIT_PENDING',
                    'COMPLETED',
                    'CANCELLED'
                ]
                for status in statuses:
                    print(f"{get_timestamp()}   - {status}")
                
                conn.execute(text("""
                    ALTER TABLE purchase_orders
                    ADD CONSTRAINT check_po_status_macro
                    CHECK (status_macro IN (
                        'DRAFT',
                        'SUBMITTED',
                        'APPROVED',
                        'IN_PROGRESS',
                        'WAITING_DISPATCH',
                        'WAITING_COMMERCIAL_PARTITION',
                        'AUDIT_PENDING',
                        'COMPLETED',
                        'CANCELLED'
                    ));
                """))
                print(f"{get_timestamp()} [SUCCESS] New constraint added")
                
                # Step 3: Verify constraint
                print(f"{get_timestamp()} [STEP 3] Verifying constraint...")
                result = conn.execute(text("""
                    SELECT conname, pg_get_constraintdef(oid) as definition
                    FROM pg_constraint
                    WHERE conname = 'check_po_status_macro';
                """))
                
                row = result.fetchone()
                if row:
                    print(f"{get_timestamp()} [SUCCESS] Constraint verified:")
                    print(f"{get_timestamp()}   Name: {row[0]}")
                    print(f"{get_timestamp()}   Definition: {row[1]}")
                else:
                    print(f"{get_timestamp()} [WARNING] Could not verify constraint")
                
                # Commit transaction
                trans.commit()
                print(f"{get_timestamp()} [SUCCESS] Transaction committed")
                
                print(f"\n{get_timestamp()} ========================================")
                print(f"{get_timestamp()} MIGRATION COMPLETED SUCCESSFULLY")
                print(f"{get_timestamp()} ========================================")
                
                return True
                
            except SQLAlchemyError as e:
                trans.rollback()
                print(f"{get_timestamp()} [ERROR] Migration failed, rolling back...")
                print(f"{get_timestamp()} [ERROR] {str(e)}")
                return False
                
    except Exception as e:
        print(f"{get_timestamp()} [ERROR] Failed to connect to database")
        print(f"{get_timestamp()} [ERROR] {str(e)}")
        return False

if __name__ == "__main__":
    print(f"\n{get_timestamp()} Starting migration script...")
    success = run_migration()
    
    if success:
        print(f"\n{get_timestamp()} ✅ Migration completed successfully!")
        print(f"{get_timestamp()} The database constraint has been updated.")
        print(f"{get_timestamp()} All status values are now valid.")
        sys.exit(0)
    else:
        print(f"\n{get_timestamp()} ❌ Migration failed!")
        print(f"{get_timestamp()} Please check the error messages above.")
        sys.exit(1)
