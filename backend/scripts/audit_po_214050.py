import sys
import os
import socket
import subprocess
import time
from sqlalchemy import text

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

def run_audit():
    proxy_proc = ensure_cloud_sql_proxy()
    db = None
    try:
        from backend.database import SessionLocal

        db = SessionLocal()
        
        print("=" * 80)
        print("READ-ONLY PRODUCTION AUDIT: PO 214050 & USER 'JADER'")
        print("=" * 80)

        # 1. Check Production Table (purchase_orders)
        print("\n--- 1. CHECK PRODUCTION TABLE (purchase_orders) ---")
        try:
            res_po = db.execute(text(
                "SELECT id, po_number, status_macro, created_at, updated_at, tenant_id, partition_metadata "
                "FROM purchase_orders WHERE po_number ILIKE '%214050%'"
            )).fetchall()
            
            if res_po:
                print(f"[FOUND] {len(res_po)} record(s) matching PO 214050:")
                for row in res_po:
                    print(f"  ID: {row.id}")
                    print(f"  PO Number: {row.po_number}")
                    print(f"  Status Macro: {row.status_macro}")
                    print(f"  Created At: {row.created_at}")
                    print(f"  Updated At: {row.updated_at}")
                    print(f"  Tenant ID: {row.tenant_id}")
                    print(f"  Partition Metadata: {row.partition_metadata}")
            else:
                print("[NOT FOUND] No record matching po_number '214050' in purchase_orders.")
        except Exception as e:
            print(f"[ERROR] purchase_orders check: {e}")
        finally:
            db.rollback()

        # 2. Check Staging Table (staging_sessions)
        print("\n--- 2. CHECK STAGING TABLE (staging_sessions) ---")
        try:
            res_staging = db.execute(text(
                "SELECT id, is_active, created_at, updated_at "
                "FROM staging_sessions WHERE CAST(data AS TEXT) ILIKE '%214050%' OR CAST(session_metadata AS TEXT) ILIKE '%214050%'"
            )).fetchall()
            
            if res_staging:
                print(f"[FOUND] {len(res_staging)} staging session(s) containing '214050':")
                for row in res_staging:
                    print(f"  Staging Session ID: {row.id} | Is Active: {row.is_active} | Created: {row.created_at} | Updated: {row.updated_at}")
            else:
                print("[NOT FOUND] No staging session containing string '214050'.")
        except Exception as e_stg:
            print(f"[INFO] Staging query fallback check...")
            try:
                res_stg_all = db.execute(text(
                    "SELECT id, created_at FROM staging_sessions WHERE CAST(data AS TEXT) ILIKE '%214050%'"
                )).fetchall()
                if res_stg_all:
                    print(f"[FOUND] {len(res_stg_all)} staging session(s): {res_stg_all}")
                else:
                    print("[NOT FOUND] No staging session containing string '214050'.")
            except Exception as e2:
                print(f"[NOT FOUND / ERROR] Staging check: {e2}")
        finally:
            db.rollback()

        # 3. Check Audit Logs (audit_logs)
        print("\n--- 3. CHECK AUDIT LOGS (audit_logs) ---")
        try:
            res_audit = db.execute(text(
                "SELECT id, action, user_id, po_id, created_at, details "
                "FROM audit_logs WHERE CAST(po_id AS TEXT) ILIKE '%214050%' OR CAST(payload AS TEXT) ILIKE '%214050%' OR CAST(details AS TEXT) ILIKE '%214050%'"
            )).fetchall()
            
            if res_audit:
                print(f"[FOUND] {len(res_audit)} audit log entry/entries matching '214050':")
                for row in res_audit:
                    print(f"  Audit ID: {row.id} | Action: {row.action} | User: {row.user_id} | PO ID: {row.po_id} | Created: {row.created_at} | Details: {row.details}")
            else:
                print("[NOT FOUND] No audit log entries matching string '214050'.")
        except Exception as e_aud:
            print(f"[INFO] Audit logs check: {e_aud}")
        finally:
            db.rollback()

        # 4. Check Order Items (order_items & POs for 'TADASHI')
        print("\n--- 4. CHECK ORDER ITEMS & POS FOR 'TADASHI' ---")
        try:
            res_items = db.execute(text(
                "SELECT id, po_id, sku, item_total_value, extra_metadata "
                "FROM order_items WHERE CAST(extra_metadata AS TEXT) ILIKE '%TADASHI%' OR CAST(extra_metadata AS TEXT) ILIKE '%214050%'"
            )).fetchall()
            
            res_tadashi_po = db.execute(text(
                "SELECT id, po_number, status_macro, created_at, partition_metadata "
                "FROM purchase_orders WHERE CAST(partition_metadata AS TEXT) ILIKE '%TADASHI%'"
            )).fetchall()

            if res_items:
                print(f"[FOUND] {len(res_items)} order item(s) matching 'TADASHI' or '214050':")
                for row in res_items:
                    print(f"  Item ID: {row.id} | PO ID: {row.po_id} | SKU: {row.sku} | Extra Meta: {row.extra_metadata}")
            else:
                print("[NOT FOUND] No order items matching 'TADASHI' or '214050' in extra_metadata.")

            if res_tadashi_po:
                print(f"[FOUND] {len(res_tadashi_po)} PO(s) with partition_metadata matching 'TADASHI':")
                for row in res_tadashi_po:
                    print(f"  PO ID: {row.id} | PO: {row.po_number} | Status: {row.status_macro} | Created: {row.created_at} | Meta: {row.partition_metadata}")
            else:
                print("[NOT FOUND] No POs matching partition_metadata ILIKE '%TADASHI%'.")
        except Exception as e_items:
            print(f"[ERROR] Order items / Tadashi check: {e_items}")
        finally:
            db.rollback()

        # 5. Audit User 'Jader'
        print("\n--- 5. AUDIT USER 'JADER' ---")
        try:
            res_users = db.execute(text(
                "SELECT id, email, name, role, area, created_at "
                "FROM users WHERE name ILIKE '%jader%' OR email ILIKE '%jader%'"
            )).fetchall()

            if res_users:
                print(f"[FOUND] {len(res_users)} user(s) matching 'jader':")
                for row in res_users:
                    print(f"  User ID: {row.id} | Name: {row.name} | Email: {row.email} | Role: {row.role} | Area: {getattr(row, 'area', 'N/A')} | Created: {row.created_at}")
            else:
                print("[NOT FOUND] No users found matching name or email 'jader'.")
        except Exception as e_usr:
            print(f"[ERROR] User audit check: {e_usr}")
        finally:
            db.rollback()

        print("=" * 80)
        print("AUDIT COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"[ERROR] Audit execution failed: {e}")
    finally:
        if db:
            db.close()
        if proxy_proc:
            proxy_proc.terminate()

if __name__ == "__main__":
    run_audit()
