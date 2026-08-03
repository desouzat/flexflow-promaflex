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
    print("🔍 DIAGNOSTIC AUDIT: SKUs 9038 & 8537")
    print("=" * 90)

    # 1. Query tenants
    tenants_q = text("SELECT id, name FROM tenants;")
    tenants = db.execute(tenants_q).fetchall()
    print("Tenants in Database:")
    for t in tenants:
        print(f"  ID: {t[0]} | Name: {t[1]}")

    # 2. Query material_costs for SKUs 9038 and 8537 across ALL tenants
    print("\n" + "-" * 90)
    query = text("""
        SELECT id, sku, nome, custo_mp_kg, rendimento, tenant_id, created_at, updated_at
        FROM material_costs 
        WHERE LOWER(TRIM(sku)) IN ('9038', '8537', '9.038', '8.537', '9,038', '8,537')
           OR sku ILIKE '%9038%' OR sku ILIKE '%8537%'
           OR nome ILIKE '%9038%' OR nome ILIKE '%8537%';
    """)
    rows = db.execute(query).fetchall()

    print(f"Matching Material Records ({len(rows)} found across all tenants):")
    print(f"{'ID':<38} | {'SKU':<15} | {'Nome':<25} | {'Custo MP':<10} | {'Rendimento':<10} | {'Tenant ID':<38}")
    print("-" * 140)
    for r in rows:
        m_id, sku, nome, custo, rendimento, tenant_id, created, updated = r
        print(f"{str(m_id):<38} | repr('{sku}') | repr('{nome}') | {custo} | {rendimento} | {tenant_id}")

    # 3. Total count of material_costs per tenant
    print("\n" + "-" * 90)
    count_q = text("SELECT tenant_id, COUNT(*) FROM material_costs GROUP BY tenant_id;")
    counts = db.execute(count_q).fetchall()
    print("Total Material Costs count per Tenant:")
    for c in counts:
        print(f"  Tenant ID: {c[0]} | Count: {c[1]}")

    print("=" * 90)

except Exception as e:
    print(f"❌ Error during DB audit: {e}")
finally:
    db.close()
    if proxy_proc:
        proxy_proc.terminate()
