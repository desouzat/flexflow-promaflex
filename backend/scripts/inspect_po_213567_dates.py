import sys
import os
import time
import subprocess
import socket

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
        print("[INFO] Cloud SQL Proxy is already running on port 5434.")
        return None

    proxy_binary = os.path.join(os.path.dirname(__file__), "../cloud-sql-proxy.exe")
    if not os.path.exists(proxy_binary):
        print(f"[WARNING] cloud-sql-proxy.exe not found at {proxy_binary}")
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

def inspect_dates():
    proxy_proc = ensure_cloud_sql_proxy()
    try:
        from backend.database import SessionLocal
        from backend.models import PurchaseOrder, OrderItem

        db = SessionLocal()
        print("\n" + "="*80)
        print("INSPECTING REAL PO 213567 DATES IN POSTGRESQL (PORT 5434)")
        print("="*80)

        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == "213567").first()
        if not po:
            print("[WARNING] PO 213567 not found in DB.")
            return

        print(f"PO ID                     : {po.id}")
        print(f"PO Number                 : {po.po_number}")
        print(f"PO Client Name            : {po.client_name}")
        print(f"PO expected_delivery_date : {getattr(po, 'expected_delivery_date', None)}")
        print(f"PO delivery_date          : {getattr(po, 'delivery_date', None)}")
        print(f"PO extra_metadata         : {getattr(po, 'extra_metadata', None)}")
        print(f"PO partition_metadata     : {getattr(po, 'partition_metadata', None)}")

        print("\n--- ITEMS FOR PO 213567 ---")
        for i, item in enumerate(po.items, start=1):
            print(f"Item #{i} SKU             : {item.sku}")
            print(f"Item #{i} extra_metadata  : {item.extra_metadata}")
        print("="*80 + "\n")
        db.close()
    finally:
        if proxy_proc:
            proxy_proc.terminate()

if __name__ == "__main__":
    inspect_dates()
