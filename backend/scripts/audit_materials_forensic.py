import sys
import os
import socket
import subprocess
import time
from sqlalchemy import text
from sqlalchemy.orm import Session

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

def run_forensic_audit():
    proxy_proc = ensure_cloud_sql_proxy()
    db = None
    try:
        from backend.database import SessionLocal
        from backend.models import MaterialCost, User

        db: Session = SessionLocal()
        print("=" * 115)
        print("FORENSIC MATERIAL COSTS AUDIT (SKUs: 8175, 9041, 6264, 901, 9015)")
        print("=" * 115)
        
        skus = ['8175', '9041', '6264', '901', '9015', '8.175', '9.041', '6.264', '901.0', '9.015']
        records = db.query(MaterialCost).filter(MaterialCost.sku.in_(skus)).all()
        
        print(f"{'SKU':<10} | {'Nome/Codigo Estruturado':<30} | {'Custo M2':<10} | {'Rendimento':<10} | {'Created At':<19} | {'Updated At':<19} | {'Updated By User'}")
        print("-" * 115)
        
        for m in records:
            updated_user = "System / Unknown (NULL)"
            if m.updated_by:
                user = db.query(User).filter(User.id == m.updated_by).first()
                if user:
                    updated_user = f"{user.name} ({user.email})"
                else:
                    updated_user = f"User UUID: {m.updated_by}"
                    
            created_at_str = m.created_at.strftime('%d/%m/%Y %H:%M:%S') if getattr(m, 'created_at', None) else "N/A"
            updated_at_str = m.updated_at.strftime('%d/%m/%Y %H:%M:%S') if m.updated_at else "N/A"
            rend_val = str(round(float(m.rendimento), 4)) if getattr(m, 'rendimento', None) else "N/A"
            custo_val = str(round(float(m.custo_mp_kg), 2)) if getattr(m, 'custo_mp_kg', None) else "N/A"
            
            print(f"{m.sku:<10} | {m.nome[:30]:<30} | {custo_val:<10} | {rend_val:<10} | {created_at_str:<19} | {updated_at_str:<19} | {updated_user}")
            
        print("=" * 115)
        db.rollback()

        # Audit Logs Check
        print("\n--- AUDIT LOGS CHECK FOR TARGET SKUs ---")
        for target_sku in ['8175', '9041', '6264', '901', '9015']:
            try:
                res_logs = db.execute(text(
                    "SELECT id, item_id, from_status, to_status, created_at, changed_by, extra_data "
                    "FROM audit_logs WHERE CAST(extra_data AS TEXT) ILIKE :sku"
                ), {"sku": f"%{target_sku}%"}).fetchall()
                
                if res_logs:
                    print(f"[FOUND] {len(res_logs)} log entry/entries for SKU {target_sku}:")
                    for row in res_logs:
                        print(f"  Audit ID: {row.id} | Item ID: {row.item_id} | {row.from_status} -> {row.to_status} | User: {row.changed_by} | Extra: {row.extra_data}")
                else:
                    print(f"[NOT FOUND] No audit log entries mentioning SKU {target_sku} in extra_data.")
            except Exception as e_log:
                print(f"[INFO] Audit log query for SKU {target_sku}: {e_log}")
            finally:
                db.rollback()
                
        print("=" * 115)

    except Exception as e:
        print(f"[ERROR] Audit failed: {str(e)}")
    finally:
        if db:
            db.close()
        if proxy_proc:
            proxy_proc.terminate()

if __name__ == "__main__":
    run_forensic_audit()
