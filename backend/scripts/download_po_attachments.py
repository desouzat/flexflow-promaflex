import sys
import os
import socket
import subprocess
import time
import json
import urllib.request
from pathlib import Path
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

def download_po_attachments():
    proxy_proc = ensure_cloud_sql_proxy()
    db = None
    try:
        from backend.database import SessionLocal
        from backend.models import PurchaseOrder, OrderItem

        db = SessionLocal()
        po_number_target = '213717'
        
        output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../scratch/po_213717"))
        os.makedirs(output_dir, exist_ok=True)
        
        print("=" * 80)
        print(f"STEP 1: QUERYING METADATA FOR PO {po_number_target}")
        print("=" * 80)

        pos = db.query(PurchaseOrder).filter(PurchaseOrder.po_number.ilike(f"%{po_number_target}%")).all()
        if not pos:
            print(f"[WARNING] No PO found matching po_number '{po_number_target}'")
            return

        urls_and_paths = set()
        po_ids = []

        for po in pos:
            po_ids.append(str(po.id))
            print(f"Found PO ID: {po.id} | PO Number: {po.po_number} | Status: {po.status_macro}")
            print(f"Partition Metadata: {json.dumps(po.partition_metadata or {}, indent=2, default=str)}")
            
            meta = po.partition_metadata or {}
            for k, v in meta.items():
                if v and isinstance(v, str) and ('http' in v or 'attachments/' in v or '.pdf' in v or '.jpg' in v or '.jpeg' in v or '.png' in v):
                    print(f"  [FOUND IN PO META] Key '{k}': {v}")
                    urls_and_paths.add((k, v))
                    
            for idx, item in enumerate(po.items, 1):
                extra = item.extra_metadata or {}
                print(f"\n  Item #{idx} (SKU: {item.sku}):")
                print(f"  Extra Metadata: {json.dumps(extra, indent=2, default=str)}")
                for k, v in extra.items():
                    if v and isinstance(v, str) and ('http' in v or 'attachments/' in v or '.pdf' in v or '.jpg' in v or '.jpeg' in v or '.png' in v):
                        print(f"    [FOUND IN ITEM EXTRA] Key '{k}': {v}")
                        urls_and_paths.add((k, v))

        # Check GCS Storage directly for PO ID or PO Number
        print("\n" + "=" * 80)
        print("STEP 2: CHECKING GCS & LOCAL STORAGE BUCKETS")
        print("=" * 80)
        
        gcs_blobs = []
        try:
            from google.cloud import storage
            local_key_path = "backend/gcp-key.json"
            if os.path.exists(local_key_path) and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath(local_key_path)
                
            storage_client = storage.Client()
            bucket_name = os.getenv("GCP_BUCKET_NAME", "flexflow-attachments-224292950652")
            bucket = storage_client.bucket(bucket_name)
            
            for pid in po_ids:
                prefix = f"attachments/{pid}/"
                print(f"[GCS LIST] Listing blobs with prefix '{prefix}'...")
                blobs = list(bucket.list_blobs(prefix=prefix))
                for blob in blobs:
                    print(f"  [GCS BLOB FOUND] {blob.name} ({blob.size} bytes)")
                    gcs_blobs.append(blob)

            # Also check prefix for po_number
            prefix_num = f"attachments/{po_number_target}/"
            print(f"[GCS LIST] Listing blobs with prefix '{prefix_num}'...")
            blobs_num = list(bucket.list_blobs(prefix=prefix_num))
            for blob in blobs_num:
                print(f"  [GCS BLOB FOUND] {blob.name} ({blob.size} bytes)")
                gcs_blobs.append(blob)
                
            # List all blobs under attachments/ to catch any matching filename or timestamp if needed
            print(f"[GCS LIST] Checking all blobs under attachments/...")
            all_blobs = list(bucket.list_blobs(prefix="attachments/"))
            for blob in all_blobs:
                if po_number_target in blob.name or any(pid in blob.name for pid in po_ids) or "124500" in blob.name or "124.500" in blob.name:
                    if blob not in gcs_blobs:
                        print(f"  [GCS BLOB MATCHED BY SEARCH] {blob.name} ({blob.size} bytes)")
                        gcs_blobs.append(blob)
        except Exception as e_gcs:
            print(f"[INFO] GCS client check notice: {e_gcs}")

        # Check local uploads fallback directory
        local_uploads_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../uploads"))
        print(f"[LOCAL CHECK] Searching local uploads dir '{local_uploads_dir}'...")
        if os.path.exists(local_uploads_dir):
            for root, dirs, files in os.walk(local_uploads_dir):
                for f in files:
                    full_p = os.path.join(root, f)
                    if any(pid in full_p for pid in po_ids) or po_number_target in full_p or "124500" in full_p:
                        print(f"  [LOCAL FILE FOUND] {full_p}")
                        # Copy to output_dir
                        dest_p = os.path.join(output_dir, f)
                        with open(full_p, "rb") as sf, open(dest_p, "wb") as df:
                            df.write(sf.read())

        # Download from GCS Blobs found
        for blob in gcs_blobs:
            safe_name = os.path.basename(blob.name)
            dest_p = os.path.join(output_dir, safe_name)
            print(f"[DOWNLOADING GCS BLOB] {blob.name} -> {dest_p}")
            blob.download_to_filename(dest_p)

        # Download from URLs/paths found in DB
        for key_name, url_or_path in urls_and_paths:
            if url_or_path.startswith("http://") or url_or_path.startswith("https://"):
                try:
                    safe_name = os.path.basename(url_or_path.split("?")[0])
                    dest_p = os.path.join(output_dir, f"{key_name}_{safe_name}")
                    print(f"[DOWNLOADING URL] {url_or_path} -> {dest_p}")
                    urllib.request.urlretrieve(url_or_path, dest_p)
                except Exception as e_dl:
                    print(f"[WARNING] Could not download URL {url_or_path}: {e_dl}")

        print("\n" + "=" * 80)
        print("STEP 3: RECOVERED FILES SUMMARY")
        print("=" * 80)
        
        recovered_files = os.listdir(output_dir)
        if not recovered_files:
            print("[NOTICE] No files saved in scratch output directory yet.")
        else:
            for fname in recovered_files:
                fpath = os.path.join(output_dir, fname)
                fsize = os.path.getsize(fpath)
                print(f"  File Name: {fname}")
                print(f"  Absolute Path: {fpath}")
                print(f"  File Size: {fsize:,} bytes")
                print("-" * 50)

    except Exception as e:
        print(f"[ERROR] Attachment download script failed: {e}")
    finally:
        if db:
            db.close()
        if proxy_proc:
            proxy_proc.terminate()

if __name__ == "__main__":
    download_po_attachments()
