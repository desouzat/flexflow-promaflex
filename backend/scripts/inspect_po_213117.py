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
from backend.models import PurchaseOrder

db: Session = SessionLocal()
try:
    print("=" * 90)
    print("🔍 INSPECT PO 213117 DATES AND METADATA")
    print("=" * 90)

    po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number.ilike("%213117%")).first()
    if po:
        print(f"PO ID: {po.id}")
        print(f"PO Number: {po.po_number}")
        print(f"Status Macro: {po.status_macro}")
        print(f"created_at: {po.created_at}")
        print(f"updated_at: {po.updated_at}")
        print(f"partition_metadata: {po.partition_metadata}")
        for idx, item in enumerate(po.items):
            print(f"  Item {idx+1}: SKU={item.sku}, extra_metadata={item.extra_metadata}")
    else:
        print("PO 213117 not found!")

    print("=" * 90)

except Exception as e:
    print(f"❌ Error inspecting PO: {e}")
finally:
    db.close()
    if proxy_proc:
        proxy_proc.terminate()
