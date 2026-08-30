import sys
import os
import socket
import subprocess
import time

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
        print(f"[INFO] cloud-sql-proxy.exe not found at {proxy_binary}, attempting direct connection.")
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

def audit_item_units():
    proxy_proc = ensure_cloud_sql_proxy()
    db = None
    try:
        from backend.database import SessionLocal
        from backend.models import PurchaseOrder, OrderItem, MaterialCost

        db = SessionLocal()
        po_numbers = ["213946", "213385"]
        
        print("=" * 80)
        print("PO & ITEM UNITS AUDIT (PO 213946 & PO 213385)")
        print("=" * 80)

        for po_num in po_numbers:
            pos = db.query(PurchaseOrder).filter(PurchaseOrder.po_number.ilike(f"%{po_num}%")).all()
            if not pos:
                print(f"\n[WARNING] No PO found matching po_number '{po_num}'")
                continue
            
            for po in pos:
                print(f"\nPO Number: {po.po_number} | Client: {po.client_name} | ID: {po.id}")
                print(f"Status: {po.status_macro} | Total Value: {po.po_total_value}")
                print("-" * 75)
                
                for idx, item in enumerate(po.items, 1):
                    extra = item.extra_metadata or {}
                    unit = getattr(item, 'unidade_medida', None) or extra.get('unidade_medida') or extra.get('unit') or extra.get('Un. Med.') or extra.get('Unidade') or 'M2'
                    qty = item.quantity or 0.0
                    width = getattr(item, 'width', None) or extra.get('largura') or extra.get('width') or extra.get('Largura (mm)') or 0
                    length = getattr(item, 'length', None) or extra.get('comprimento') or extra.get('length') or extra.get('Comprimento (m)') or 0
                    
                    # Material cost
                    mat = db.query(MaterialCost).filter(MaterialCost.sku == item.sku, MaterialCost.tenant_id == po.tenant_id).first()
                    cost_mp_kg = mat.custo_mp_kg if mat else "N/A"
                    rendimento = mat.rendimento if mat else "N/A"
                    mat_nome = mat.nome if mat else "N/A"

                    print(f"  Item #{idx}: SKU: {item.sku} | Name: {item.product_description or item.sku}")
                    print(f"    Unidade Medida: {unit} | Qty: {qty} | Width (mm): {width} | Length (m): {length}")
                    print(f"    Unit Value: {item.unit_value} | Price: {item.price}")
                    print(f"    Material: {mat_nome}")
                    print(f"    material.custo_mp_kg (cost/m2): {cost_mp_kg} | material.rendimento (m2/kg): {rendimento}")
                    print("-" * 50)

    except Exception as e:
        print(f"[ERROR] Audit failed: {e}")
    finally:
        if db:
            db.close()
        if proxy_proc:
            proxy_proc.terminate()

if __name__ == "__main__":
    audit_item_units()
