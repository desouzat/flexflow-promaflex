"""
Database Audit Script for Partition Feature
Verifies that all database schema changes are actually present in PostgreSQL
"""
import sys
import os

# Add parent directory to path for imports
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, backend_dir)
os.chdir(backend_dir)

from sqlalchemy import inspect, text
from database import engine, SessionLocal
from models import PurchaseOrder
import traceback

def audit_database():
    """Perform comprehensive database audit"""
    print("=" * 80)
    print("DATABASE AUDIT - PARTITION FEATURE VERIFICATION")
    print("=" * 80)
    
    results = {
        "success": True,
        "checks": []
    }
    
    try:
        # Check 1: Verify database connection
        print("\n[CHECK 1] Database Connection")
        print("-" * 80)
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✓ Connected to PostgreSQL")
            print(f"  Version: {version[:50]}...")
            results["checks"].append({"name": "DB Connection", "status": "PASS"})
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        results["success"] = False
        results["checks"].append({"name": "DB Connection", "status": "FAIL", "error": str(e)})
        return results
    
    # Check 2: Verify purchase_orders table exists
    print("\n[CHECK 2] Purchase Orders Table Existence")
    print("-" * 80)
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if "purchase_orders" in tables:
            print(f"✓ Table 'purchase_orders' exists")
            results["checks"].append({"name": "Table Exists", "status": "PASS"})
        else:
            print(f"✗ Table 'purchase_orders' NOT FOUND")
            print(f"  Available tables: {tables}")
            results["success"] = False
            results["checks"].append({"name": "Table Exists", "status": "FAIL"})
            return results
    except Exception as e:
        print(f"✗ Error checking table: {e}")
        results["success"] = False
        results["checks"].append({"name": "Table Exists", "status": "FAIL", "error": str(e)})
        return results
    
    # Check 3: Verify partition columns exist
    print("\n[CHECK 3] Partition Columns Verification")
    print("-" * 80)
    try:
        columns = inspector.get_columns("purchase_orders")
        column_names = [col["name"] for col in columns]
        
        required_columns = ["parent_po_id", "is_partitioned"]
        missing_columns = []
        
        for col in required_columns:
            if col in column_names:
                col_info = next(c for c in columns if c["name"] == col)
                print(f"✓ Column '{col}' exists")
                print(f"  Type: {col_info['type']}")
                print(f"  Nullable: {col_info['nullable']}")
            else:
                print(f"✗ Column '{col}' NOT FOUND")
                missing_columns.append(col)
        
        if missing_columns:
            print(f"\n✗ MISSING COLUMNS: {missing_columns}")
            results["success"] = False
            results["checks"].append({"name": "Partition Columns", "status": "FAIL", "missing": missing_columns})
        else:
            results["checks"].append({"name": "Partition Columns", "status": "PASS"})
            
    except Exception as e:
        print(f"✗ Error checking columns: {e}")
        traceback.print_exc()
        results["success"] = False
        results["checks"].append({"name": "Partition Columns", "status": "FAIL", "error": str(e)})
        return results
    
    # Check 4: Verify WAITING_COMMERCIAL_PARTITION status in enum
    print("\n[CHECK 4] Enum Status Verification")
    print("-" * 80)
    try:
        with engine.connect() as conn:
            # Check if the enum type exists and contains our status
            result = conn.execute(text("""
                SELECT enumlabel 
                FROM pg_enum 
                WHERE enumtypid = (
                    SELECT oid FROM pg_type WHERE typname = 'postatus'
                )
                ORDER BY enumsortorder
            """))
            enum_values = [row[0] for row in result.fetchall()]
            
            print(f"✓ Found POStatus enum with {len(enum_values)} values:")
            for val in enum_values:
                marker = "★" if val == "WAITING_COMMERCIAL_PARTITION" else " "
                print(f"  {marker} {val}")
            
            if "WAITING_COMMERCIAL_PARTITION" in enum_values:
                print(f"\n✓ WAITING_COMMERCIAL_PARTITION status exists in database enum")
                results["checks"].append({"name": "Enum Status", "status": "PASS"})
            else:
                print(f"\n✗ WAITING_COMMERCIAL_PARTITION status NOT FOUND in enum")
                results["success"] = False
                results["checks"].append({"name": "Enum Status", "status": "FAIL"})
                
    except Exception as e:
        print(f"✗ Error checking enum: {e}")
        traceback.print_exc()
        results["success"] = False
        results["checks"].append({"name": "Enum Status", "status": "FAIL", "error": str(e)})
    
    # Check 5: Verify Python model has the status
    print("\n[CHECK 5] Python Model Verification")
    print("-" * 80)
    try:
        if hasattr(PurchaseOrder, 'STATUS_WAITING_COMMERCIAL_PARTITION'):
            print(f"✓ PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION exists in Python model")
            print(f"  Value: {PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION}")
            
            # Check if it's in VALID_STATUSES
            if PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION in PurchaseOrder.VALID_STATUSES:
                print(f"✓ Status is in VALID_STATUSES list")
            else:
                print(f"✗ Status NOT in VALID_STATUSES list")
                results["success"] = False
            
            results["checks"].append({"name": "Python Model", "status": "PASS"})
        else:
            print(f"✗ STATUS_WAITING_COMMERCIAL_PARTITION NOT FOUND in PurchaseOrder model")
            print(f"  Available statuses: {PurchaseOrder.VALID_STATUSES}")
            results["success"] = False
            results["checks"].append({"name": "Python Model", "status": "FAIL"})
    except Exception as e:
        print(f"✗ Error checking Python model: {e}")
        results["success"] = False
        results["checks"].append({"name": "Python Model", "status": "FAIL", "error": str(e)})
    
    # Check 6: Verify foreign key constraint
    print("\n[CHECK 6] Foreign Key Constraint Verification")
    print("-" * 80)
    try:
        foreign_keys = inspector.get_foreign_keys("purchase_orders")
        parent_fk = None
        
        for fk in foreign_keys:
            if "parent_po_id" in fk.get("constrained_columns", []):
                parent_fk = fk
                break
        
        if parent_fk:
            print(f"✓ Foreign key constraint found for parent_po_id")
            print(f"  References: {parent_fk['referred_table']}.{parent_fk['referred_columns']}")
            print(f"  Constraint: {parent_fk.get('name', 'N/A')}")
            results["checks"].append({"name": "Foreign Key", "status": "PASS"})
        else:
            print(f"⚠ No foreign key constraint found for parent_po_id")
            print(f"  This may be intentional if using application-level constraints")
            results["checks"].append({"name": "Foreign Key", "status": "WARNING"})
            
    except Exception as e:
        print(f"✗ Error checking foreign keys: {e}")
        results["checks"].append({"name": "Foreign Key", "status": "WARNING", "error": str(e)})
    
    # Summary
    print("\n" + "=" * 80)
    print("AUDIT SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for c in results["checks"] if c["status"] == "PASS")
    failed = sum(1 for c in results["checks"] if c["status"] == "FAIL")
    warnings = sum(1 for c in results["checks"] if c["status"] == "WARNING")
    
    print(f"Total Checks: {len(results['checks'])}")
    print(f"✓ Passed: {passed}")
    print(f"✗ Failed: {failed}")
    print(f"⚠ Warnings: {warnings}")
    
    if results["success"]:
        print("\n🎉 DATABASE AUDIT: SUCCESS")
        print("All critical partition feature schema changes are present in PostgreSQL")
    else:
        print("\n❌ DATABASE AUDIT: FAILED")
        print("Some critical schema changes are missing")
    
    print("=" * 80)
    
    return results

if __name__ == "__main__":
    try:
        results = audit_database()
        sys.exit(0 if results["success"] else 1)
    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        traceback.print_exc()
        sys.exit(1)
