import sys
import os
import socket
import subprocess
import time
import uuid
from datetime import datetime

# Ensure backend path is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

def is_port_open(port=5434):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.5)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

def ensure_cloud_sql_proxy():
    if is_port_open(5434):
        print("[INFO] Cloud SQL Proxy is running on port 5434.")
        return None

    proxy_binary = os.path.join(os.path.dirname(__file__), "../cloud-sql-proxy.exe")
    if not os.path.exists(proxy_binary):
        print(f"[INFO] cloud-sql-proxy.exe not found at {proxy_binary}, using default DB configuration.")
        return None

    gcloud_cmd = r"C:\Users\Thiago\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    try:
        print("[INFO] Fetching GCP access token...")
        token_out = subprocess.check_output([gcloud_cmd, 'auth', 'print-access-token'], stderr=subprocess.STDOUT)
        token = token_out.decode().strip()
        
        print("[INFO] Starting Cloud SQL Proxy tunnel on port 5434...")
        proc = subprocess.Popen([
            proxy_binary,
            'flexflow-promaflex:southamerica-east1:flexflow-db-v1',
            '--port', '5434',
            '--token', token
        ])
        time.sleep(3.5)
        return proc
    except Exception as err:
        print(f"[WARNING] Could not start Cloud SQL Proxy: {err}")
        return None

def cancel_pos():
    proxy_proc = ensure_cloud_sql_proxy()
    db = None
    try:
        from backend.database import SessionLocal
        from backend.models import PurchaseOrder, AuditLog, User, get_last_audit_hash

        db = SessionLocal()
        target_pos = ['213935', '213848', '213550']
        tenant_id = uuid.UUID('23c431b9-da55-4098-9628-c86df8070b7c') # PromaFlex tenant
        user_uuid = uuid.UUID('a39e3176-55ac-460e-bcd2-958068737b0b') # Admin Thiago
        
        # Check if user exists
        user = db.query(User).filter(User.id == user_uuid).first()
        if not user:
            # Fallback to any active admin if user_uuid not found
            admin_user = db.query(User).filter(User.tenant_id == tenant_id, User.role == 'admin').first()
            if admin_user:
                user_uuid = admin_user.id
                print(f"[INFO] Using Admin User ID: {user_uuid} ({admin_user.name})")

        pos = db.query(PurchaseOrder).filter(
            PurchaseOrder.tenant_id == tenant_id,
            PurchaseOrder.po_number.in_(target_pos)
        ).all()
        
        print(f"Found {len(pos)} POs to cancel: {[p.po_number for p in pos]}")
        now_utc = datetime.utcnow()
        
        for po in pos:
            old_status = po.status_macro
            po.status_macro = 'CANCELLED'
            po.updated_at = now_utc
            
            client_name = po.client_name or "Cliente Desconhecido"

            # Update status for each order item and create audit log
            if po.items and len(po.items) > 0:
                for item in po.items:
                    item_old_status = item.status_item or old_status
                    item.status_item = 'CANCELLED'
                    item.updated_at = now_utc
                    
                    previous_hash = get_last_audit_hash(db, item.id)
                    audit_hash = AuditLog.calculate_hash_for_version(
                        version=AuditLog.HASH_VERSION_CURRENT,
                        tenant_id=po.tenant_id,
                        item_id=item.id,
                        from_status=item_old_status,
                        to_status='CANCELLED',
                        timestamp=now_utc,
                        previous_hash=previous_hash,
                        changed_by=user_uuid
                    )
                    
                    audit_entry = AuditLog(
                        item_id=item.id,
                        from_status=item_old_status,
                        to_status='CANCELLED',
                        hash=audit_hash,
                        previous_hash=previous_hash,
                        hash_version=AuditLog.HASH_VERSION_CURRENT,
                        is_exception=False,
                        justification='Cancelamento cirurgico de PO com quantidade <= 1 (Cancelado no ONET)',
                        changed_by=user_uuid,
                        extra_data={
                            "action": "MANUAL_CANCELLATION",
                            "po_id": str(po.id),
                            "po_number": po.po_number,
                            "client_name": client_name,
                            "details": "Cancelamento cirurgico de PO com quantidade <= 1 (Cancelado no ONET)",
                            "user_id": str(user_uuid),
                            "cancelled_at": now_utc.isoformat()
                        }
                    )
                    db.add(audit_entry)
            
            print(f"  - PO #{po.po_number} ({client_name}): {old_status} -> CANCELLED")

        db.commit()
        print("SUCCESS: All 3 POs successfully cancelled with audit trail committed!")

    except Exception as e:
        if db:
            db.rollback()
        print(f"ERROR: {str(e)}")
    finally:
        if db:
            db.close()
        if proxy_proc:
            proxy_proc.terminate()

if __name__ == "__main__":
    cancel_pos()
