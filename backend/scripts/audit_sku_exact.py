import os
import sys
import time
import subprocess
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

workspace_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(workspace_root))

proxy_binary = workspace_root / "backend" / "cloud-sql-proxy.exe"

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
        time.sleep(3.5)
    except Exception as e:
        print(f"[WARNING] Could not auto-launch proxy: {e}")

from backend.database import SessionLocal

db: Session = SessionLocal()
try:
    print("=" * 90)
    print("🔍 AUDIT EXACT SKU 9083 AND VARIANTS")
    print("=" * 90)

    query = text("""
        SELECT id, sku, nome, custo_mp_kg, rendimento, tenant_id, created_at, updated_at
        FROM material_costs 
        WHERE LOWER(TRIM(sku)) IN ('9083', '9.083', '9,083', '9083.0', '9083,0')
           OR sku ILIKE '%9083%' OR sku ILIKE '%9,083%';
    """)
    rows = db.execute(query).fetchall()

    print(f"\nExact/Variant SKUs found ({len(rows)} records):")
    for r in rows:
        print(f"ID: {r[0]} | SKU: repr({repr(r[1])}) | Nome: repr({repr(r[2])}) | Custo: {r[3]} | Tenant: {r[5]}")

    # Check unique constraint on material_costs
    constraints_q = text("""
        SELECT conname, pg_get_constraintdef(c.oid)
        FROM pg_constraint c
        JOIN pg_namespace n ON n.oid = c.connamespace
        WHERE conrelid = 'material_costs'::regclass;
    """)
    constraints = db.execute(constraints_q).fetchall()
    print("\nConstraints on material_costs:")
    for c in constraints:
        print(f"Constraint: {c[0]} | Def: {c[1]}")

    # Check search query logic on CostsPage.jsx or costs router
    print("=" * 90)

except Exception as e:
    print(f"❌ Error during exact audit: {e}")
finally:
    db.close()
    if proxy_proc:
        proxy_proc.terminate()
