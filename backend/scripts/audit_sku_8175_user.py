import sys
import os
import socket
import subprocess
import time
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

def audit_skus():
    proxy_proc = ensure_cloud_sql_proxy()
    db = None
    try:
        from backend.database import SessionLocal
        from backend.models import MaterialCost, User

        db: Session = SessionLocal()
        print("==========================================================================================")
        print("AUDITING MATERIAL COSTS FOR SKUs 8175 AND 9041")
        print("==========================================================================================")
        
        skus = ['8175', '9041', '8.175', '9.041']
        records = db.query(MaterialCost).filter(MaterialCost.sku.in_(skus)).all()
        
        print(f"{'SKU':<10} | {'Nome/Codigo Estruturado':<25} | {'Custo M2':<10} | {'Updated At':<20} | {'Updated By User'}")
        print("-" * 105)
        
        for m in records:
            updated_user = "System / Unknown"
            if m.updated_by:
                user = db.query(User).filter(User.id == m.updated_by).first()
                if user:
                    updated_user = f"{user.name} ({user.email})"
                else:
                    updated_user = f"User UUID: {m.updated_by}"
                    
            updated_at_str = m.updated_at.strftime('%d/%m/%Y %H:%M:%S') if m.updated_at else "N/A"
            print(f"{m.sku:<10} | {m.nome[:25]:<25} | {m.custo_mp_kg:<10} | {updated_at_str:<20} | {updated_user}")
            
        print("==========================================================================================")
            
    except Exception as e:
        print(f"[ERROR] Audit failed: {str(e)}")
    finally:
        if db:
            db.close()
        if proxy_proc:
            proxy_proc.terminate()

if __name__ == "__main__":
    audit_skus()
