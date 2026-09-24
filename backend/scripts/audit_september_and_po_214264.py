import sys
import os
import socket
import subprocess
import time
import json
from pathlib import Path
from sqlalchemy import text
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

def run_audit():
    proxy_proc = ensure_cloud_sql_proxy()
    db = None
    try:
        from backend.database import SessionLocal
        from backend.models import PurchaseOrder, OrderItem

        db = SessionLocal()
        
        print("=" * 100)
        print("STEP 1: SEARCHING FOR PO 214264 IN DATABASE, STAGING & AUDIT LOGS")
        print("=" * 100)

        # 1.1 purchase_orders table
        res_po = db.execute(text(
            "SELECT id, po_number, status_macro, created_at, updated_at, tenant_id, partition_metadata "
            "FROM purchase_orders WHERE po_number ILIKE '%214264%'"
        )).fetchall()

        if res_po:
            print(f"[FOUND IN purchase_orders] {len(res_po)} record(s) matching PO 214264:")
            for row in res_po:
                print(f"  ID: {row.id}")
                print(f"  PO Number: {row.po_number}")
                print(f"  Status Macro: {row.status_macro}")
                print(f"  Created At: {row.created_at}")
                print(f"  Updated At: {row.updated_at}")
                print(f"  Partition Metadata: {row.partition_metadata}")
        else:
            print("[NOT FOUND] No record matching po_number '214264' in purchase_orders.")
        db.rollback()

        # 1.2 order_items table
        res_items = db.execute(text(
            "SELECT id, po_id, sku, item_total_value, extra_metadata "
            "FROM order_items WHERE CAST(extra_metadata AS TEXT) ILIKE '%214264%'"
        )).fetchall()

        if res_items:
            print(f"[FOUND IN order_items] {len(res_items)} item(s) containing '214264':")
            for row in res_items:
                print(f"  Item ID: {row.id} | PO ID: {row.po_id} | SKU: {row.sku} | Extra: {row.extra_metadata}")
        else:
            print("[NOT FOUND] No order items containing string '214264' in extra_metadata.")
        db.rollback()

        # 1.3 staging_sessions table
        try:
            res_staging = db.execute(text(
                "SELECT id, is_active, created_at, updated_at "
                "FROM staging_sessions WHERE CAST(data AS TEXT) ILIKE '%214264%' OR CAST(session_metadata AS TEXT) ILIKE '%214264%'"
            )).fetchall()

            if res_staging:
                print(f"[FOUND IN staging_sessions] {len(res_staging)} staging session(s) containing '214264':")
                for row in res_staging:
                    print(f"  Session ID: {row.id} | Is Active: {row.is_active} | Created: {row.created_at} | Updated: {row.updated_at}")
            else:
                print("[NOT FOUND] No staging session containing string '214264'.")
        except Exception as e_stg:
            print(f"[INFO] Staging session check: {e_stg}")
        finally:
            db.rollback()

        # 1.4 audit_logs table
        try:
            res_audit = db.execute(text(
                "SELECT id, item_id, from_status, to_status, created_at, changed_by, extra_data "
                "FROM audit_logs WHERE CAST(extra_data AS TEXT) ILIKE '%214264%' OR CAST(justification AS TEXT) ILIKE '%214264%'"
            )).fetchall()

            if res_audit:
                print(f"[FOUND IN audit_logs] {len(res_audit)} audit log entry/entries containing '214264':")
                for row in res_audit:
                    print(f"  Audit ID: {row.id} | Item: {row.item_id} | {row.from_status} -> {row.to_status} | Created: {row.created_at} | Extra: {row.extra_data}")
            else:
                print("[NOT FOUND] No audit log entries containing string '214264'.")
        except Exception as e_aud:
            print(f"[INFO] Audit log check: {e_aud}")
        finally:
            db.rollback()

        print("\n" + "=" * 100)
        print("STEP 2: SEPTEMBER 2026 VOLUME AUDIT (DISTINCT POS VS ITEM ROWS)")
        print("=" * 100)

        # 2.1 Distinct PO Count in September 2026
        po_count_res = db.execute(text(
            "SELECT COUNT(DISTINCT id) FROM purchase_orders "
            "WHERE created_at >= '2026-09-01 00:00:00'"
        )).scalar()

        # 2.2 Order Items Count for September 2026 POs
        items_count_res = db.execute(text(
            "SELECT COUNT(oi.id) "
            "FROM order_items oi "
            "JOIN purchase_orders po ON oi.po_id = po.id "
            "WHERE po.created_at >= '2026-09-01 00:00:00'"
        )).scalar()

        # 2.3 Status macro breakdown for September POs
        status_breakdown = db.execute(text(
            "SELECT status_macro, COUNT(DISTINCT id) as po_count "
            "FROM purchase_orders "
            "WHERE created_at >= '2026-09-01 00:00:00' "
            "GROUP BY status_macro ORDER BY po_count DESC"
        )).fetchall()

        avg_items_per_po = (items_count_res / po_count_res) if po_count_res and po_count_res > 0 else 0

        print(f"1. Total Distinct Purchase Orders (POs) created in Sept 2026 : {po_count_res}")
        print(f"2. Total Item Rows (Line Items) for Sept 2026 POs         : {items_count_res}")
        print(f"3. Average Item Rows per PO                              : {avg_items_per_po:.2f} items/PO")
        print(f"4. Total Export Rows generated by CSV/Kanban Export      : {items_count_res} rows")

        print("\nSeptember 2026 PO Status Macro Breakdown:")
        for sb in status_breakdown:
            print(f"  - {sb.status_macro:<25}: {sb.po_count} POs")

        db.rollback()

        print("\n" + "=" * 100)
        print("STEP 3: CHECKING S3 BUCKET FILES FOR PO 214264")
        print("=" * 100)

        # Load environment variables from backend/.env
        env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.env"))
        if os.path.exists(env_path):
            with open(env_path, encoding="utf-8") as ef:
                for eline in ef:
                    eline = eline.strip()
                    if eline and not eline.startswith("#") and "=" in eline:
                        ek, _, ev = eline.partition("=")
                        os.environ.setdefault(ek.strip(), ev.strip())

        s3_endpoint = os.getenv('S3_ENDPOINT')
        s3_access_key = os.getenv('S3_ACCESS_KEY')
        s3_secret_key = os.getenv('S3_SECRET_KEY')
        s3_bucket = os.getenv('S3_BUCKET_NAME', 'flexflow')

        if s3_access_key and s3_secret_key:
            try:
                import boto3
                from botocore.config import Config

                s3_client = boto3.client(
                    's3',
                    endpoint_url=s3_endpoint if s3_endpoint else None,
                    aws_access_key_id=s3_access_key,
                    aws_secret_access_key=s3_secret_key,
                    config=Config(signature_version="s3v4")
                )

                print(f"[S3 CHECK] Listing objects in bucket '{s3_bucket}'...")
                paginator = s3_client.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=s3_bucket)

                all_s3_files = []
                for page in pages:
                    for obj in page.get('Contents', []):
                        all_s3_files.append(obj)

                all_s3_files.sort(key=lambda x: x['LastModified'], reverse=True)
                print(f"[S3 CHECK] Total files in bucket: {len(all_s3_files)}")
                print("\nTop 10 Most Recent Files in S3 Bucket:")
                for sobj in all_s3_files[:10]:
                    print(f"  - Key: {sobj['Key']} | LastModified: {sobj['LastModified']} | Size: {sobj['Size']:,} bytes")

                # Check recent files content or key names for 214264
                matched_s3_keys = [s['Key'] for s in all_s3_files if '214264' in s['Key']]
                if matched_s3_keys:
                    print(f"\n[FOUND IN S3 KEYS] Matched S3 file keys: {matched_s3_keys}")
                else:
                    print("\n[S3 KEY SEARCH] No S3 file key contains string '214264'.")

                # Inspect content of the 5 most recent S3 Excel/CSV files
                import pandas as pd
                import io

                print("\nInspecting contents of recent S3 spreadsheet files for PO 214264...")
                found_in_content = False
                for sobj in all_s3_files[:8]:
                    key = sobj['Key']
                    if not (key.endswith('.xlsx') or key.endswith('.xls') or key.endswith('.csv')):
                        continue

                    try:
                        obj_data = s3_client.get_object(Bucket=s3_bucket, Key=key)['Body'].read()
                        if key.endswith('.csv'):
                            df = pd.read_csv(io.BytesIO(obj_data))
                        else:
                            df = pd.read_excel(io.BytesIO(obj_data))

                        # Search string representation of dataframe
                        df_str = df.astype(str)
                        matches = df_str.apply(lambda col: col.str.contains('214264', case=False, na=False)).any(axis=1)
                        if matches.any():
                            found_in_content = True
                            matched_rows = df[matches]
                            print(f"\n[FOUND IN S3 FILE CONTENT] Match inside file '{key}':")
                            print(matched_rows.head(10).to_string())
                    except Exception as e_parse:
                        print(f"  [INFO] Could not parse file '{key}': {e_parse}")

                if not found_in_content:
                    print("[NOT FOUND IN S3 CONTENT] String '214264' was NOT found in any recent S3 spreadsheet content.")

            except Exception as e_s3:
                print(f"[S3 CHECK NOTICE] {e_s3}")
        else:
            print("[INFO] S3 environment variables not present — skipping S3 check.")

        print("\n" + "=" * 100)
        print("AUDIT COMPLETE")
        print("=" * 100)

    except Exception as e:
        print(f"[ERROR] Audit failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if db:
            db.close()
        if proxy_proc:
            proxy_proc.terminate()

if __name__ == "__main__":
    run_audit()
