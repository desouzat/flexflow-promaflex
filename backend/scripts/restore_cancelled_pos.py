import os
import sys
import time
import datetime
import subprocess
from pathlib import Path
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
        print("[INFO] Obtaining GCP Auth Token for Cloud SQL Proxy...")
        token_out = subprocess.check_output(['gcloud.cmd', 'auth', 'print-access-token'], stderr=subprocess.STDOUT)
        token = token_out.decode().strip()
        
        print("[INFO] Starting Cloud SQL Proxy tunnel on port 5434...")
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
from backend.models import PurchaseOrder

db: Session = SessionLocal()
try:
    # 1. Target: POs under the PromaFlex tenant that are currently CANCELLED
    # and were updated/modified today (July 21, 2026)
    today_start = datetime.datetime(2026, 7, 21, 0, 0, 0)
    
    pos_to_restore = db.query(PurchaseOrder).filter(
        PurchaseOrder.tenant_id == '23c431b9-da55-4098-9628-c86df8070b7c', # PromaFlex
        PurchaseOrder.status_macro == 'CANCELLED',
        PurchaseOrder.updated_at >= today_start
    ).all()
    
    print("==========================================================================================")
    print(f"🔍 AUDITING POs FOR RESTORATION (Found: {len(pos_to_restore)} candidates cancelled today)")
    print("==========================================================================================")
    print(f"{'PO Number':<10} | {'Client':<40} | {'Created At':<20} | {'Cancelled At':<20}")
    print("-" * 100)
    
    restored_count = 0
    for po in pos_to_restore:
        # Format dates for clear visual audit
        created_str = po.created_at.strftime('%d/%m/%Y %H:%M:%S') if po.created_at else "N/A"
        updated_str = po.updated_at.strftime('%d/%m/%Y %H:%M:%S') if po.updated_at else "N/A"
        
        client_disp = (po.client_name or "")[:40]
        print(f"{po.po_number:<10} | {client_disp:<40} | {created_str:<20} | {updated_str:<20}")
        
        # Move back to APPROVED (PCP column)
        po.status_macro = 'APPROVED'
        po.updated_at = datetime.datetime.utcnow()
        restored_count += 1
        
    print("-" * 100)
    
    if restored_count > 0:
        db.commit()
        print(f"✅ SUCCESS: Audit passed! Successfully restored {restored_count} POs back to APPROVED (PCP)!")
    else:
        print("[WARNING] No POs were updated because none matched the criteria.")
        db.rollback()
    print("==========================================================================================")
        
except Exception as e:
    db.rollback()
    print(f"❌ ERROR during restore transaction: {str(e)}")
finally:
    db.close()
    if proxy_proc:
        proxy_proc.terminate()
