import sys
import os
import socket
import subprocess
import time
import json

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
        return None

    proxy_binary = os.path.join(os.path.dirname(__file__), "../cloud-sql-proxy.exe")
    if not os.path.exists(proxy_binary):
        return None

    gcloud_cmd = r"C:\Users\Thiago\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    try:
        token_out = subprocess.check_output([gcloud_cmd, 'auth', 'print-access-token'], stderr=subprocess.STDOUT)
        token = token_out.decode().strip()
        
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

proxy_proc = ensure_cloud_sql_proxy()

from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import PurchaseOrder, OrderItem, AuditLog

db: Session = SessionLocal()
try:
    target_pos = ['214441', '213127']
    print("=" * 90)
    print("🔍 AUDITORIA FORENSE DE DATAS E SLA - POs #214441 e #213127")
    print("=" * 90)
    
    pos = db.query(PurchaseOrder).filter(PurchaseOrder.po_number.in_(target_pos)).all()
    
    if not pos:
        print("⚠️ Nenhuma das POs foi encontrada no banco!")
    
    for po in pos:
        print(f"\n📦 PEDIDO #{po.po_number} (ID: {po.id})")
        print(f"   Status Macro: {po.status_macro}")
        print(f"   Created At (DB): {po.created_at}")
        print(f"   Updated At (DB): {po.updated_at}")
        
        # Partition Metadata
        meta = po.partition_metadata or {}
        print("\n   --- PARTITION METADATA (Cabeçalho da PO) ---")
        print(f"   • expected_delivery_date (SLA Topo): {meta.get('expected_delivery_date')}")
        print(f"   • order_date (Data do Pedido):       {meta.get('order_date')}")
        print(f"   • order_entry_date (Dt. Entrega):    {meta.get('order_entry_date')}")
        print(f"   • data_programada (Agendamento PCP): {meta.get('data_programada')}")
        print(f"   • data_faturamento / billing_date:   {meta.get('data_faturamento') or meta.get('billing_date')}")
        
        # Items
        print(f"\n   --- ITENS DO PEDIDO ({len(po.items)} itens) ---")
        for idx, item in enumerate(po.items, 1):
            i_meta = item.extra_metadata or {}
            print(f"   Item {idx} (SKU: {item.sku}):")
            print(f"     - extra_metadata['billing_date']: {i_meta.get('billing_date')}")
            print(f"     - extra_metadata['delivery_date']: {i_meta.get('delivery_date')}")
            print(f"     - extra_metadata['order_date']:    {i_meta.get('order_date')}")
            print(f"     - extra_metadata['data_faturamento']: {i_meta.get('data_faturamento')}")
            
        # Audit Logs regarding date changes
        print("\n   --- HISTÓRICO DE AUDITORIA DE STATUS / MUTAÇÕES ---")
        item_ids = [i.id for i in po.items]
        if item_ids:
            audits = db.query(AuditLog).filter(
                AuditLog.item_id.in_(item_ids)
            ).order_by(AuditLog.created_at.desc()).limit(10).all()
            for a in audits:
                print(f"     [{a.created_at}] STATUS: {a.from_status} -> {a.to_status} | Just: {a.justification}")
        else:
            print("     (Nenhum item encontrado)")

        handoffs = meta.get("handoff_history") or []
        if handoffs:
            print("   --- HANDOFF HISTORY (Metadata) ---")
            for h in handoffs:
                print(f"     [{h.get('timestamp')}] {h.get('action')}: {h.get('from_status')} -> {h.get('to_status')} | User: {h.get('user')} | Obs: {h.get('comment') or h.get('reason')}")
            
        print("-" * 90)

    # ALSO: Investigate how the datepicker in KanbanPage.jsx binds its value
    print("\n🔎 VERIFICAÇÃO CONCLUÍDA. AGUARDANDO ANÁLISE DOS DADOS.")
    
except Exception as e:
    print(f"ERRO: {e}")
finally:
    db.close()
    if proxy_proc:
        proxy_proc.terminate()
