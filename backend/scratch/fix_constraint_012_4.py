import psycopg2
import sys

# Try 5433 first (active port seen in netstat), then 5434 (proxy)
CANDIDATES = [
    "postgresql://flexflow_app:Souza%40123@127.0.0.1:5433/flexflow_prod",
    "postgresql://flexflow_app:Souza%40123@127.0.0.1:5434/flexflow_prod",
    "postgresql://postgres:Souza%40123@127.0.0.1:5433/flexflow_prod",
    "postgresql://postgres@127.0.0.1:5433/flexflow_prod",
]

conn = None
used_dsn = None
for dsn in CANDIDATES:
    try:
        conn = psycopg2.connect(dsn, connect_timeout=3)
        used_dsn = dsn
        print(f"CONNECTION OK via: {dsn.split('@')[1]}")
        break
    except Exception as e:
        print(f"  Failed {dsn.split('@')[1]}: {e}")

if conn is None:
    print("[FATAL] Could not connect to any PostgreSQL instance. Proxy must be started.")
    sys.exit(1)

conn.autocommit = False
cur = conn.cursor()

print("=== STEP 1: Drop old constraint ===")
cur.execute("ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS check_po_status_macro")
print("  DROP: OK")

print("=== STEP 2: Recreate with WAITING_COMMERCIAL_PARTITION ===")
cur.execute("""
ALTER TABLE purchase_orders ADD CONSTRAINT check_po_status_macro CHECK (
    status_macro IN (
        'DRAFT', 'SUBMITTED', 'PCP', 'APPROVED', 'MANUFACTURING',
        'BILLING', 'SHIPPING', 'WAITING_DISPATCH',
        'ARCHIVED', 'ARCHIVED_PARTITIONED', 'COMPLETED', 'CANCELLED',
        'WAITING_COMMERCIAL_PARTITION'
    )
)
""")
print("  ADD: OK")
conn.commit()
print("  COMMIT: OK")

print("=== STEP 3: Verify in pg_constraint ===")
cur.execute("""
    SELECT conname, pg_get_constraintdef(oid)
    FROM pg_constraint
    WHERE conname = 'check_po_status_macro'
""")
row = cur.fetchone()
if row:
    print("  Constraint name:", row[0])
    print("  Definition     :", row[1])
    if "WAITING_COMMERCIAL_PARTITION" in row[1]:
        print("  [PASS] WAITING_COMMERCIAL_PARTITION present in constraint.")
    else:
        print("  [FAIL] WAITING_COMMERCIAL_PARTITION MISSING from constraint!")
        sys.exit(1)
else:
    print("  [FAIL] Constraint not found in pg_constraint!")
    sys.exit(1)

cur.close()
conn.close()
print("=== MIGRATION COMPLETE ===")
sys.exit(0)
