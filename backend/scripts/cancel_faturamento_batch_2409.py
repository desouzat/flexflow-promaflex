import sys
import os
import socket
import subprocess
import time
import uuid
import datetime
from datetime import datetime as dt_class

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

def main():
    proxy_proc = ensure_cloud_sql_proxy()
    db = None
    try:
        from backend.database import SessionLocal
        from backend.models import PurchaseOrder, OrderItem, AuditLog, User, get_last_audit_hash

        db = SessionLocal()
        target_pos_map = {
            '213255': 'ATENDIDO COM DEVOLUCAO',
            '213881': 'ATENDIDO COM DEVOLUCAO',
            '213930': 'ATENDIDO COM DEVOLUCAO',
            '214311': 'PEDIDO CANCELADO',
            '213971': 'PEDIDO CANCELADO'
        }
        target_pos = list(target_pos_map.keys())
        tenant_str = '23c431b9-da55-4098-9628-c86df8070b7c' # PromaFlex
        tenant_uuid = uuid.UUID(tenant_str)
        user_uuid = uuid.UUID('a39e3176-55ac-460e-bcd2-958068737b0b') # Admin Thiago

        # Verify user
        user = db.query(User).filter(User.id == user_uuid).first()
        if not user:
            admin_user = db.query(User).filter(User.tenant_id == tenant_uuid, User.role == 'admin').first()
            if admin_user:
                user_uuid = admin_user.id

        pos = db.query(PurchaseOrder).filter(
            (PurchaseOrder.tenant_id == tenant_uuid) | (PurchaseOrder.tenant_id == tenant_str),
            PurchaseOrder.po_number.in_(target_pos)
        ).all()

        found_numbers = [p.po_number for p in pos]
        print(f"Found {len(pos)} of {len(target_pos)} POs to cancel: {found_numbers}")

        missing = set(target_pos) - set(found_numbers)
        if missing:
            print(f"WARNING: The following POs were not found in tenant {tenant_str}: {missing}")

        now_utc = datetime.datetime.utcnow()

        for po in pos:
            old_status = po.status_macro
            po.status_macro = 'CANCELLED'
            po.updated_at = now_utc
            reason = target_pos_map.get(po.po_number, 'CANCELADO NO ONET')
            details_text = f"Cancelamento solicitado via e-mail pelo Faturamento em 24/09/2026. Motivo: {reason}"

            # Store SLA justification / reason on PO header as well
            po.sla_justification_category = reason
            po.sla_justification_text = details_text
            po.sla_justification_user = "Faturamento / Anderson"
            po.sla_justification_at = now_utc

            # Defensive cancellation of items (handling status / status_item)
            if po.items and len(po.items) > 0:
                for item in po.items:
                    item_old_status = getattr(item, 'status_item', None) or getattr(item, 'status', None) or old_status
                    if hasattr(item, 'status'):
                        item.status = 'CANCELLED'
                    if hasattr(item, 'status_item'):
                        item.status_item = 'CANCELLED'
                    if hasattr(item, 'updated_at'):
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

                    audit = AuditLog(
                        item_id=item.id,
                        from_status=item_old_status,
                        to_status='CANCELLED',
                        hash=audit_hash,
                        previous_hash=previous_hash,
                        hash_version=AuditLog.HASH_VERSION_CURRENT,
                        is_exception=False,
                        justification=details_text,
                        changed_by=user_uuid,
                        extra_data={
                            "action": "MANUAL_CANCELLATION",
                            "po_id": str(po.id),
                            "po_number": po.po_number,
                            "reason": reason,
                            "details": details_text,
                            "requested_by": "Faturamento / Anderson Moreno",
                            "requested_at": "24/09/2026"
                        }
                    )
                    db.add(audit)

            # Client name defensive lookup
            client_name = getattr(po, 'client_name', None)
            if not client_name and hasattr(po, 'partition_metadata') and isinstance(po.partition_metadata, dict):
                client_name = po.partition_metadata.get('client_name')
            client_str = (client_name or 'N/A')[:35]

            print(f"  - PO #{po.po_number} ({client_str}): {old_status} -> CANCELLED [{reason}]")

        db.commit()
        print(f"\nSUCCESS: All {len(pos)} POs and their items successfully cancelled with audit trail committed!")

    except Exception as e:
        if db:
            db.rollback()
        print(f"ERROR during cancellation transaction: {str(e)}")
    finally:
        if db:
            db.close()
        if proxy_proc:
            proxy_proc.terminate()

if __name__ == "__main__":
    main()
