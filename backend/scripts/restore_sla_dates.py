"""
FlexFlow Production Database Maintenance Script: CR-DATES SLA Restoration
Restores overwritten expected_delivery_date (contractual SLA) from item billing_date.

Usage:
    python backend/scripts/restore_sla_dates.py --dry-run
    python backend/scripts/restore_sla_dates.py --commit
    python backend/scripts/restore_sla_dates.py --po-number 213127 --dry-run
    python backend/scripts/restore_sla_dates.py --po-number 213127 --commit
"""

import sys
import os
import socket
import subprocess
import time
import argparse
from datetime import datetime, date

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
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3.5)
        return proc
    except Exception as err:
        print(f"[WARNING] Could not start Cloud SQL Proxy: {err}")
        return None


def normalize_to_iso_date(date_val):
    """Convert DD/MM/YYYY or YYYY-MM-DD into YYYY-MM-DD."""
    if not date_val:
        return None
    s = str(date_val).strip().split("T")[0]
    if "/" in s:
        parts = s.split("/")
        if len(parts) == 3:
            d, m, y = parts
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    elif "-" in s:
        parts = s.split("-")
        if len(parts) == 3:
            y, m, d = parts
            return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    return None


def main():
    parser = argparse.ArgumentParser(description="Restore overwritten SLA expected_delivery_date from item billing_date.")
    parser.add_argument("--commit", action="store_true", help="Persist database changes (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Simulate restoration without saving")
    parser.add_argument("--po-number", type=str, default=None, help="Specific PO number to target")
    args = parser.parse_args()

    is_commit = args.commit
    target_po = args.po_number

    proxy_proc = ensure_cloud_sql_proxy()

    try:
        from sqlalchemy.orm import Session
        from sqlalchemy.orm.attributes import flag_modified
        from backend.database import SessionLocal
        from backend.models import PurchaseOrder, OrderItem, AuditLog, get_last_audit_hash

        db: Session = SessionLocal()

        print("=" * 90)
        mode_str = "🔴 LIVE COMMIT MODE (CHANGES WILL BE PERSISTED)" if is_commit else "🟡 DRY-RUN MODE (SIMULATION ONLY - NO WRITES)"
        print(f"🛠️  RESTAURAÇÃO DE DATAS DE SLA (CR-DATES) — {mode_str}")
        if target_po:
            print(f"🎯 PO ALVO ESPECÍFICA: #{target_po}")
        print("=" * 90)

        query = db.query(PurchaseOrder)
        if target_po:
            query = query.filter(PurchaseOrder.po_number == target_po)
        pos = query.all()

        candidates = []
        for po in pos:
            meta = po.partition_metadata or {}
            exp_date_raw = meta.get("expected_delivery_date")
            prog_date_raw = meta.get("data_programada")

            if not exp_date_raw or not prog_date_raw:
                continue

            exp_iso = normalize_to_iso_date(exp_date_raw)
            prog_iso = normalize_to_iso_date(prog_date_raw)

            # Check if expected_delivery_date was overwritten by data_programada
            if exp_iso == prog_iso:
                # Find original contractual billing_date from items
                item_billing_raw = None
                for item in po.items:
                    im = item.extra_metadata or {}
                    b_date = im.get("billing_date") or im.get("data_faturamento")
                    if b_date:
                        item_billing_raw = b_date
                        break

                if item_billing_raw:
                    item_billing_iso = normalize_to_iso_date(item_billing_raw)
                    if item_billing_iso and item_billing_iso != prog_iso:
                        candidates.append({
                            "po": po,
                            "po_number": po.po_number,
                            "status": po.status_macro,
                            "current_sla": exp_iso,
                            "data_programada": prog_iso,
                            "original_billing": item_billing_raw,
                            "target_sla": item_billing_iso
                        })

        print(f"\n📊 Total de POs inspecionadas: {len(pos)}")
        print(f"⚠️  POs detectadas com sobrescrita de SLA: {len(candidates)}\n")

        if not candidates:
            print("✅ Nenhuma PO encontrada com discrepância de SLA.")
            return

        print(f"{'PO #':<10} | {'STATUS':<15} | {'SLA ATUAL (ERRADO)':<20} | {'DATA PROGRAMADA':<16} | {'SLA RESTAURADO (ALVO)'}")
        print("-" * 90)
        for c in candidates:
            print(f"{c['po_number']:<10} | {c['status']:<15} | {c['current_sla']:<20} | {c['data_programada']:<16} | {c['target_sla']} ({c['original_billing']})")

        if is_commit:
            print("\n" + "=" * 90)
            print("🚀 APLICANDO RESTAURAÇÃO NO BANCO DE DADOS...")
            print("=" * 90)

            for c in candidates:
                po = c["po"]
                meta = dict(po.partition_metadata or {})
                old_sla = meta.get("expected_delivery_date")
                new_sla = c["target_sla"]

                meta["expected_delivery_date"] = new_sla
                meta["sla_restored_at"] = datetime.utcnow().isoformat()
                meta["sla_restored_from_billing"] = c["original_billing"]
                po.partition_metadata = meta
                flag_modified(po, "partition_metadata")

                # Also update model property setter
                po.expected_delivery_date = new_sla
                po.updated_at = datetime.utcnow()

                # Audit log ledger entry
                if po.items and len(po.items) > 0:
                    first_item = po.items[0]
                    prev_hash = get_last_audit_hash(db, first_item.id)
                    audit_entry = AuditLog(
                        item_id=first_item.id,
                        from_status=po.status_macro,
                        to_status=po.status_macro,
                        hash=f"cr_dates_restore_{po.po_number}_{int(time.time())}",
                        previous_hash=prev_hash,
                        is_exception=False,
                        justification=f"[CR-DATES] Restauração de SLA contratual: {old_sla} -> {new_sla} (base Dt.Faturamento)",
                        created_at=datetime.utcnow()
                    )
                    db.add(audit_entry)

                print(f"  ✅ PO #{po.po_number}: SLA restaurado com sucesso para {new_sla}.")

            db.commit()
            print("\n🎉 Todas as alterações foram persistidas no PostgreSQL com sucesso!")
        else:
            print("\nℹ️  Modo Dry-Run concluído. Nenhuma alteração foi gravada.")
            print("   Para aplicar estas correções permanentemente, execute com a flag --commit:")
            if target_po:
                print(f"   python backend/scripts/restore_sla_dates.py --po-number {target_po} --commit")
            else:
                print("   python backend/scripts/restore_sla_dates.py --commit")

    except Exception as e:
        print(f"❌ ERRO durante restauração: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'db' in locals() and db:
            db.close()
        if proxy_proc:
            proxy_proc.terminate()


if __name__ == "__main__":
    main()
