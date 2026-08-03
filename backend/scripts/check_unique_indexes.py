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
from backend.models import MaterialCost, Tenant

db: Session = SessionLocal()
try:
    print("=" * 90)
    print("🔍 CHECK UNIQUE INDEXES AND TEST INSERT FOR SKU 9083")
    print("=" * 90)

    indexes_q = text("""
        SELECT indexname, indexdef
        FROM pg_indexes
        WHERE tablename = 'material_costs';
    """)
    indexes = db.execute(indexes_q).fetchall()
    print("Indexes on material_costs:")
    for idx in indexes:
        print(f"  Name: {idx[0]} | Def: {idx[1]}")

    # Check tenant
    tenant = db.query(Tenant).first()
    tenant_id = tenant.id if tenant else None
    print(f"\nTenant ID: {tenant_id}")

    # Test simulating creation of 9083
    print("\nTesting dry-run insert of SKU '9083':")
    db.begin_nested()
    try:
        new_mat = MaterialCost(
            tenant_id=tenant_id,
            sku="9083",
            nome="XMV 2020",
            custo_mp_kg=5.12,
            rendimento=1.0,
            indice_impostos=0.0
        )
        db.add(new_mat)
        db.flush()
        print("  ✅ Dry-run insert succeeded! SKU 9083 can be inserted cleanly without DB constraint violation.")
    except Exception as err:
        print(f"  ❌ Dry-run insert FAILED: {err}")
    finally:
        db.rollback()

    print("=" * 90)

except Exception as e:
    print(f"❌ Error: {e}")
finally:
    db.close()
    if proxy_proc:
        proxy_proc.terminate()
