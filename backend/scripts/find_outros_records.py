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
    print("=" * 80)
    print("🔍 SUPPLEMENTARY READ-ONLY AUDIT: IDENTIFYING 'OUTROS' RECORDS")
    print("=" * 80)

    # 1. Query Purchase Orders
    print("\n--- 1. Purchase Orders with business_unit IN ('Outros', 'OUTROS') ---")
    po_query = text("""
        SELECT id, po_number, partition_metadata->>'client_name' AS client_name, created_at, partition_metadata->>'business_unit' as bu
        FROM purchase_orders
        WHERE partition_metadata->>'business_unit' IN ('Outros', 'OUTROS');
    """)
    pos = db.execute(po_query).fetchall()
    print(f"Total POs found: {len(pos)}")
    for p_id, po_num, client, created_at, bu in pos:
        created_str = created_at.strftime('%d/%m/%Y %H:%M:%S') if created_at else "N/A"
        print(f"  • PO Number: {po_num:<12} | Client: {client:<40} | Created At: {created_str} | Unit: {bu}")

    # 2. Query Client Preferences
    print("\n--- 2. Client Preferences with business_unit IN ('Outros', 'OUTROS') ---")
    cp_query = text("""
        SELECT id, client_name, business_unit, updated_at
        FROM client_preferences
        WHERE business_unit IN ('Outros', 'OUTROS');
    """)
    cps = db.execute(cp_query).fetchall()
    print(f"Total Client Preferences found: {len(cps)}")
    for cp_id, client_name, bu, updated_at in cps:
        updated_str = updated_at.strftime('%d/%m/%Y %H:%M:%S') if updated_at else "N/A"
        print(f"  • Client Name: {client_name:<45} | Business Unit: {bu:<10} | Updated At: {updated_str}")

    print("=" * 80)

except Exception as e:
    print(f"❌ Error during query: {e}")
finally:
    db.close()
    if proxy_proc:
        proxy_proc.terminate()
