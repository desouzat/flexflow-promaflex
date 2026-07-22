import os
import sys
import time
import subprocess
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

# Fix Windows console encoding issues
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory of backend (workspace root) to sys.path
workspace_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(workspace_root))

proxy_binary = workspace_root / "backend" / "cloud-sql-proxy.exe"

# Start Proxy with token if binary exists
proxy_proc = None
if proxy_binary.exists():
    try:
        token_out = subprocess.check_output(['gcloud.cmd', 'auth', 'print-access-token'], stderr=subprocess.STDOUT)
        token = token_out.decode().strip()

        proxy_proc = subprocess.Popen([
            str(proxy_binary),
            'flexflow-promaflex:southamerica-east1:flexflow-db-v1',
            '--port', '5434',
            '--token', token
        ])
        time.sleep(3.5) # Wait for proxy socket listener to open
    except Exception as e:
        print(f"[WARNING] Could not auto-launch proxy: {e}")

from backend.database import SessionLocal

db: Session = SessionLocal()
try:
    print("=" * 80)
    print("🔍 READ-ONLY DB SCHEMA & BUSINESS UNIT AUDIT")
    print("=" * 80)

    # 1. Check constraints on purchase_orders table
    print("\n--- 1. CHECK CONSTRAINTS ON purchase_orders ---")
    constraints_q = text("""
        SELECT conname, pg_get_constraintdef(c.oid) AS constraint_def
        FROM pg_constraint c
        JOIN pg_namespace n ON n.oid = c.connamespace
        JOIN pg_class cl ON cl.oid = c.conrelid
        WHERE cl.relname = 'purchase_orders';
    """)
    constraints = db.execute(constraints_q).fetchall()
    if constraints:
        for conname, condef in constraints:
            print(f"Constraint: {conname} -> {condef}")
    else:
        print("No constraints found on purchase_orders.")

    # 2. Check enum types in postgres
    print("\n--- 2. CHECK ENUM TYPES IN POSTGRES ---")
    enum_q = text("""
        SELECT t.typname, e.enumlabel
        FROM pg_type t
        JOIN pg_enum e ON t.oid = e.enumtypid
        JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
        ORDER BY t.typname, e.enumsortorder;
    """)
    enums = db.execute(enum_q).fetchall()
    if enums:
        for typname, label in enums:
            print(f"Enum {typname}: {label}")
    else:
        print("No Postgres user-defined ENUMs found.")

    # 3. Check column data types for purchase_orders
    print("\n--- 3. COLUMN DATA TYPES FOR purchase_orders ---")
    cols_q = text("""
        SELECT column_name, data_type, character_maximum_length, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'purchase_orders' AND column_name LIKE '%unidade%' OR column_name LIKE '%unit%' OR column_name LIKE '%partition%';
    """)
    cols = db.execute(cols_q).fetchall()
    for col, dtype, maxlen, nullable in cols:
        print(f"Column: {col} | Data Type: {dtype} | MaxLen: {maxlen} | Nullable: {nullable}")

    # 4. Audit existing data in purchase_orders partition_metadata or other fields
    print("\n--- 4. AUDIT EXISTING VALUES IN purchase_orders ---")
    # Inspect distinct partition_metadata -> business_unit or client_preferences
    po_units_q = text("""
        SELECT 
            partition_metadata->>'business_unit' AS bu_meta,
            COUNT(*) 
        FROM purchase_orders 
        GROUP BY bu_meta;
    """)
    po_units = db.execute(po_units_q).fetchall()
    print("Purchase Orders business_unit in partition_metadata:")
    for bu, count in po_units:
        print(f"  '{bu}': {count} POs")

    # 5. Check client_preferences table
    print("\n--- 5. CHECK client_preferences TABLE ---")
    cp_units_q = text("""
        SELECT business_unit, COUNT(*)
        FROM client_preferences
        GROUP BY business_unit;
    """)
    try:
        cp_units = db.execute(cp_units_q).fetchall()
        print("ClientPreferences business_unit count:")
        for bu, count in cp_units:
            print(f"  '{bu}': {count} entries")
    except Exception as e:
        print(f"ClientPreferences table query: {e}")

    print("\n" + "=" * 80)
    print("READ-ONLY DB AUDIT COMPLETE")
    print("=" * 80)

except Exception as e:
    print(f"❌ ERROR during DB audit: {e}")
finally:
    db.close()
    if proxy_proc:
        proxy_proc.terminate()
