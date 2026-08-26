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

def test_po_213086_full_vp():
    proxy_proc = ensure_cloud_sql_proxy()
    db = None
    try:
        from backend.database import SessionLocal
        from backend.models import PurchaseOrder, OrderItem, MaterialCost
        from backend.routers.kanban import parse_payment_terms_to_days

        db = SessionLocal()
        print("\n" + "="*80)
        print("MANDATORY AUDIT VERIFICATION: PO 213086 VP DISCOUNT & DYNAMIC ICMS TRACE")
        print("="*80)

        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == "213086").first()
        if not po:
            print("[ERROR] PO 213086 not found in DB.")
            return

        item = po.items[0] if po.items else None
        extra = item.extra_metadata or {} if item else {}
        
        payment_terms_raw = extra.get('payment_terms') or '28/35/42 DDL'
        if 'ddl' not in payment_terms_raw.lower():
            payment_terms_str = f"{payment_terms_raw} DDL"
        else:
            payment_terms_str = payment_terms_raw

        payment_days = parse_payment_terms_to_days(payment_terms_str)
        qty = float(item.quantity)
        price = float(item.price)
        gross_value = qty * price

        vp_factor = pow(1.025, payment_days / 30.0)
        vp = round(gross_value / vp_factor, 2)
        vp_discount = round(gross_value - vp, 2)

        raw_icms_rate = float(extra.get('icms_percent') or extra.get('icms_rate') or 18.0)
        total_tax_rate = 9.25 + raw_icms_rate
        taxes = round(vp * (total_tax_rate / 100.0), 2)
        commission = round(vp * 0.025, 2)

        mat = db.query(MaterialCost).filter(MaterialCost.sku == item.sku).first()
        unit_cost = (float(mat.custo_mp_kg) * float(mat.rendimento)) if mat else 18.591
        industrial_cost = round(qty * unit_cost, 2)

        receita_liquida = round(vp - taxes - commission, 2)
        lucro_liquido = round(receita_liquida - industrial_cost, 2)
        margem_final = round((lucro_liquido / gross_value) * 100.0, 2)

        print("\nEXACT FINANCIAL TRACE FOR PO 213086 (DEXFLEX ARTEFATOS ADESIVOS LTDA):")
        print(f"Valor Bruto: R$ {gross_value:,.2f}")
        print(f"Condição de Pagamento: '{payment_terms_str}' -> {payment_days:.1f} days")
        print(f"Ajuste VP (-2.5%/mo): -R$ {vp_discount:,.2f}")
        print(f"Valor Presente (VP): R$ {vp:,.2f}")
        print(f"Impostos ({total_tax_rate:.2f}% = 9.25% + {raw_icms_rate:.0f}% ICMS): -R$ {taxes:,.2f}")
        print(f"Comissão (2.5%): -R$ {commission:,.2f}")
        print(f"Receita Líquida: R$ {receita_liquida:,.2f}")
        print(f"Custo Industrial: -R$ {industrial_cost:,.2f}")
        print(f"Lucro Líquido: R$ {lucro_liquido:,.2f}")
        print(f"Margem Final (%): {margem_final:.2f}%")

    finally:
        if db:
            db.close()
        if proxy_proc:
            proxy_proc.terminate()

if __name__ == "__main__":
    test_po_213086_full_vp()
