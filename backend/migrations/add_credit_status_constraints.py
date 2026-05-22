"""
Migration: Add Credit Status Constraints
Updates check constraints check_po_status_macro and check_item_status.

Run with: python backend/migrations/add_credit_status_constraints.py
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
    Update constraints to include new financial approval statuses.
    """
    print(f"{get_timestamp()} ========================================")
    print(f"{get_timestamp()} MIGRATION: Add Credit Status Constraints")
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
                # Step 1: Drop existing check_po_status_macro constraint
                print(f"{get_timestamp()} [STEP 1] Dropping check_po_status_macro...")
                conn.execute(text("""
                    ALTER TABLE purchase_orders
                    DROP CONSTRAINT IF EXISTS check_po_status_macro;
                """))
                
                # Step 2: Add check_po_status_macro constraint with ANALISE_CREDITO
                print(f"{get_timestamp()} [STEP 2] Adding check_po_status_macro with ANALISE_CREDITO...")
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
                        'CANCELLED',
                        'ANALISE_CREDITO'
                    ));
                """))
                print(f"{get_timestamp()} [SUCCESS] purchase_orders constraint updated")
                
                # Step 3: Drop existing check_item_status constraint
                print(f"{get_timestamp()} [STEP 3] Dropping check_item_status...")
                conn.execute(text("""
                    ALTER TABLE order_items
                    DROP CONSTRAINT IF EXISTS check_item_status;
                """))
                
                # Step 4: Add check_item_status constraint with credit & finance statuses
                print(f"{get_timestamp()} [STEP 4] Adding check_item_status with credit & finance statuses...")
                conn.execute(text("""
                    ALTER TABLE order_items
                    ADD CONSTRAINT check_item_status
                    CHECK (status_item IN (
                        'PENDING',
                        'ORDERED',
                        'RECEIVED',
                        'QUALITY_CHECK',
                        'APPROVED',
                        'REJECTED',
                        'CANCELLED',
                        'ANALISE_CREDITO',
                        'FINANCE_APPROVED',
                        'FINANCE_REJECTED'
                    ));
                """))
                print(f"{get_timestamp()} [SUCCESS] order_items constraint updated")
                
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
    success = run_migration()
    sys.exit(0 if success else 1)
