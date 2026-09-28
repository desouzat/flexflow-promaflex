import sys
import os
import socket
import subprocess
import time
from pathlib import Path

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

def is_port_open(port=5434):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.5)
    result = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return result == 0

def ensure_cloud_sql_proxy():
    if is_port_open(5434):
        print("[INFO] Cloud SQL Proxy is already running on port 5434.")
        return None

    proxy_binary = os.path.join(os.path.dirname(__file__), "../cloud-sql-proxy.exe")
    if not os.path.exists(proxy_binary):
        print(f"[INFO] cloud-sql-proxy.exe not found at {proxy_binary}.")
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
        from sqlalchemy.orm import Session
        from backend.database import SessionLocal
        from backend.models import User

        db = SessionLocal()
        # Enable can_cancel_commercial for all users in Comercial area or specific emails
        users = db.query(User).filter(
            (User.area.ilike('%comercial%')) | 
            (User.email.in_(['mairla@promaflex.com.br', 'abimael@promaflex.com.br', 'comercial@promaflex.com.br', 'andrea@promaflex.com.br']))
        ).all()
        
        print(f"Found {len(users)} commercial users to update:")
        for u in users:
            u.can_cancel_commercial = True
            print(f"  - Activated can_cancel_commercial for {u.email} ({u.name}) - Area: {u.area}")
        
        db.commit()
        print("SUCCESS: Commercial cancellation flags committed to PostgreSQL!")
    except Exception as e:
        if db:
            db.rollback()
        print(f"ERROR: {e}")
    finally:
        if db:
            db.close()
        if proxy_proc:
            print("[INFO] Terminating Cloud SQL Proxy tunnel process...")
            proxy_proc.terminate()

if __name__ == "__main__":
    main()
