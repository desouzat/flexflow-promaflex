import os
import sys
import time
import datetime
import subprocess
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import desc

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
from backend.models import PurchaseOrder, OrderItem, AuditLog

db: Session = SessionLocal()
try:
    # Exact stage mapping derived from audit_logs transition history
    TARGET_STAGES = {
        # 3 POs originally in SHIPPING
        "213113": "SHIPPING",
        "213096": "SHIPPING",
        "213098": "SHIPPING",

        # 3 POs originally in BILLING
        "213097": "BILLING",
        "213116": "BILLING",
        "213114": "BILLING",

        # 15 POs originally in APPROVED (PCP)
        "213100": "APPROVED",
        "213101": "APPROVED",
        "213102": "APPROVED",
        "213103": "APPROVED",
        "213104": "APPROVED",
        "213105": "APPROVED",
        "213106": "APPROVED",
        "213107": "APPROVED",
        "213108": "APPROVED",
        "213109": "APPROVED",
        "213110": "APPROVED",
        "213111": "APPROVED",
        "213112": "APPROVED",
        "213115": "APPROVED",
        "213099": "APPROVED",
    }

    target_po_numbers = list(TARGET_STAGES.keys())

    print("==========================================================================================")
    print("🔍 RESTORING POs TO THEIR ORIGINAL PRE-CANCELLATION STAGES")
    print("==========================================================================================")
    print(f"{'PO Number':<10} | {'Client':<35} | {'Accidental':<12} | {'Original Stage':<15}")
    print("-" * 100)

    restored_count = 0
    billing_count = 0
    shipping_count = 0
    pcp_count = 0

    for po_number in target_po_numbers:
        po = db.query(PurchaseOrder).filter(
            PurchaseOrder.tenant_id == '23c431b9-da55-4098-9628-c86df8070b7c',
            PurchaseOrder.po_number == po_number
        ).first()

        if po:
            original_stage = TARGET_STAGES.get(po_number, "APPROVED")
            
            current_accidental = po.status_macro or "APPROVED"
            po.status_macro = original_stage
            po.updated_at = datetime.datetime.utcnow()
            restored_count += 1

            if original_stage == "BILLING":
                billing_count += 1
            elif original_stage == "SHIPPING":
                shipping_count += 1
            else:
                pcp_count += 1

            client_disp = (po.client_name or "")[:35]
            print(f"{po.po_number:<10} | {client_disp:<35} | {current_accidental:<12} -> {original_stage:<15} (Restored!)")

    print("-" * 100)
    if restored_count > 0:
        db.commit()
        print(f"✅ SUCCESS: All {restored_count} POs restored to exact departments! (PCP: {pcp_count}, BILLING: {billing_count}, SHIPPING: {shipping_count})")
    else:
        db.rollback()
        print("[WARNING] No POs were updated.")
    print("==========================================================================================")

except Exception as e:
    db.rollback()
    print(f"❌ ERROR during database transaction: {str(e)}")
finally:
    db.close()
    if proxy_proc:
        proxy_proc.terminate()
