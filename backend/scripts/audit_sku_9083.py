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
    print("🔍 AUDIT DATABASE FOR SKU 9083 / XMV 2020")
    print("=" * 90)

    query = text("""
        SELECT id, sku, nome, custo_mp_kg, rendimento, tenant_id, created_at, updated_at
        FROM material_costs 
        WHERE sku ILIKE '%9083%' OR sku ILIKE '%9.083%' OR nome ILIKE '%xmv%' OR sku ILIKE '%xmv%';
    """)
    rows = db.execute(query).fetchall()

    print(f"\nFound {len(rows)} matching material records:")
    print(f"{'ID':<38} | {'SKU':<15} | {'Nome':<25} | {'Custo MP':<10} | {'Rendimento':<10} | {'Tenant ID':<38}")
    print("-" * 140)
    for r in rows:
        m_id, sku, nome, custo, rendimento, tenant_id, created, updated = r
        print(f"{str(m_id):<38} | '{sku}' | '{nome}' | {custo} | {rendimento} | {tenant_id}")

    print("\n" + "=" * 90)

    # Also list all material_costs count and sample SKUs to see if there's whitespace or formatting
    all_q = text("SELECT sku, nome, tenant_id FROM material_costs ORDER BY sku LIMIT 20;")
    sample_rows = db.execute(all_q).fetchall()
    print("Sample SKUs in material_costs:")
    for r in sample_rows:
        print(f"SKU: repr('{r[0]}') | Nome: repr('{r[1]}') | Tenant: {r[2]}")

    print("=" * 90)

except Exception as e:
    print(f"❌ Error during DB audit: {e}")
finally:
    db.close()
    if proxy_proc:
        proxy_proc.terminate()
