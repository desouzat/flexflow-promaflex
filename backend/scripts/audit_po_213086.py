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

def parse_payment_terms_to_days(terms):
    if not terms: return 0
    t = str(terms).lower().strip()
    if 'à vista' in t or 'a vista' in t or 'imediato' in t or '0 dias' in t: return 0
    import re
    nums = [int(n) for n in re.findall(r'\d+', t)]
    return sum(nums) / len(nums) if nums else 0

def audit_po_213086():
    proxy_proc = ensure_cloud_sql_proxy()
    db = None
    try:
        from backend.database import SessionLocal
        from backend.models import PurchaseOrder, OrderItem, MaterialCost

        db = SessionLocal()
        print("\n" + "="*80)
        print("READ-ONLY FINANCIAL AUDIT: PO 213086 MARGIN & INDUSTRIAL COST TRACE")
        print("="*80)

        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == "213086").first()
        if not po:
            print("[WARNING] PO 213086 not found in DB.")
            return

        total_price_po = sum(float(item.price) * float(item.quantity) for item in po.items) if po.items else 0.0

        print("\n1. PURCHASE ORDER DATA:")
        print(f"   PO Number     : {po.po_number}")
        print(f"   Client Name   : {po.client_name}")
        print(f"   Status Macro  : {po.status_macro}")
        print(f"   Total Price   : R$ {total_price_po:,.2f}")
        print(f"   PO Total Val  : R$ {float(po.po_total_value or 0):,.2f}")
        print(f"   Part Metadata : {po.partition_metadata}")

        print("\n2. ORDER ITEMS DATA (order_items):")
        total_costs_calc = 0.0
        terms_str = None
        for idx, item in enumerate(po.items, 1):
            qty = float(item.quantity)
            price = float(item.price)
            item_total = qty * price
            extra = item.extra_metadata or {}
            desc = extra.get('description') or extra.get('descricao') or extra.get('produto') or 'N/A'
            terms_str = extra.get('payment_terms') or terms_str
            print(f"   Item #{idx}:")
            print(f"     ID          : {item.id}")
            print(f"     SKU         : {item.sku}")
            print(f"     Description : {desc}")
            print(f"     Qty         : {qty}")
            print(f"     Unit Price  : R$ {price:,.2f}")
            print(f"     Total Price : R$ {item_total:,.2f}")
            print(f"     PaymentTerm : {terms_str}")
            print(f"     Extra Meta  : {extra}")

        print("\n3. MATCHING MATERIAL COST RECORDS (material_costs):")
        mat_tax_index = 22.25
        for item in po.items:
            mat = db.query(MaterialCost).filter(MaterialCost.sku == item.sku).first()
            if not mat:
                mat = db.query(MaterialCost).filter(MaterialCost.sku.ilike(f"%{item.sku}%")).first()
            
            if mat:
                unit_cost = float(mat.custo_mp_kg) * float(mat.rendimento)
                mat_tax_index = float(mat.indice_impostos or 22.25)
                total_costs_calc += float(item.quantity) * unit_cost
                print(f"   SKU: {item.sku}")
                print(f"     Nome            : {mat.nome}")
                print(f"     Custo MP/kg     : R$ {float(mat.custo_mp_kg):,.4f}")
                print(f"     Rendimento      : {float(mat.rendimento):,.4f} kg/un")
                print(f"     Índice Impostos : {mat_tax_index:,.2f}%")
                print(f"     Unit Cost       : R$ {unit_cost:,.4f}")
                print(f"     Total Cost Item : R$ {(float(item.quantity) * unit_cost):,.2f}")
            else:
                print(f"   SKU: {item.sku} -> No record found in material_costs table.")

        print("\n4. CURRENT CALCULATION TRACE & STEP-BY-STEP BREAKDOWN:")
        gross = total_price_po
        payment_days = parse_payment_terms_to_days(terms_str)
        vp_factor = pow(1.025, payment_days / 30)
        vp = round(gross / vp_factor, 2)
        vp_discount = round(gross - vp, 2)

        commission = round(vp * 0.025, 2)
        freight = 0.0
        costs = round(total_costs_calc, 2) if total_costs_calc > 0 else 4090.02

        # 9.25% Tax Rate
        taxes_925 = round(vp * 0.0925, 2)
        abs_margin_925 = round(vp - taxes_925 - commission - freight, 2)
        net_profit_925 = round(abs_margin_925 - costs, 2)

        # 22.25% Tax Rate
        taxes_2225 = round(vp * 0.2225, 2)
        abs_margin_2225 = round(vp - taxes_2225 - commission - freight, 2)
        net_profit_2225 = round(abs_margin_2225 - costs, 2)

        print(f"   Gross Revenue (parsedGross) : R$ {gross:,.2f}")
        print(f"   Payment Terms               : '{terms_str}' -> {payment_days:.1f} avg days (VP factor = {vp_factor:.4f})")
        print(f"   VP (Present Value)          : R$ {vp:,.2f} (VP Discount = R$ {vp_discount:,.2f})")
        print(f"   Commission (2.5% of VP)     : R$ {commission:,.2f}")
        print(f"   Freight                     : R$ {freight:,.2f}")
        print(f"   Industrial Cost (total)     : R$ {costs:,.2f}")
        print(f"   ------------------------------------------------------------")
        print(f"   [SCENARIO A: 9.25% PIS/COFINS TAX RATE]")
        print(f"     Taxes (9.25%)             : R$ {taxes_925:,.2f}")
        print(f"     Receita Líquida           : R$ {abs_margin_925:,.2f}")
        print(f"     Lucro Líquido             : R$ {net_profit_925:,.2f}")
        print(f"     Net Margin % over Gross   : {(net_profit_925 / gross * 100):.2f}%")
        print(f"     Net Margin % over VP      : {(net_profit_925 / vp * 100):.2f}%")
        print(f"   ------------------------------------------------------------")
        print(f"   [SCENARIO B: 22.25% STANDARD TAX RATE (ICMS + PIS/COFINS)]")
        print(f"     Taxes (22.25%)            : R$ {taxes_2225:,.2f}")
        print(f"     Receita Líquida           : R$ {abs_margin_2225:,.2f}")
        print(f"     Lucro Líquido             : R$ {net_profit_2225:,.2f}")
        print(f"     Net Margin % over Gross   : {(net_profit_2225 / gross * 100):.2f}%")
        print(f"     Net Margin % over VP      : {(net_profit_2225 / vp * 100):.2f}%")

        print("\n5. MARGIN RATIOS COMPARISON MATRIX FOR PO 213086:")
        print(f"   1. Legacy Bug (abs_margin_925 / costs)          : {(abs_margin_925 / costs * 100):.2f}%  (Old displayed value: 136.71%)")
        print(f"   2. Net Profit over Industrial Cost (9.25% Tax)   : {(net_profit_925 / costs * 100):.2f}%")
        print(f"   3. Net Profit over Gross Revenue (9.25% Tax)     : {(net_profit_925 / gross * 100):.2f}%")
        print(f"   4. Net Profit over Present Value (9.25% Tax)     : {(net_profit_925 / vp * 100):.2f}%")
        print(f"   5. Net Profit over Gross Revenue (22.25% Tax)    : {(net_profit_2225 / gross * 100):.2f}%  <-- (10.6% target if 22.25% taxes applied on PO total R$ 6.979,05)")
        print(f"   6. Net Profit over Present Value (22.25% Tax)    : {(net_profit_2225 / vp * 100):.2f}%")

        # Sensitivity with PO Total Value R$ 6.979,05 vs R$ 6.359,04
        po_tot_val = float(po.po_total_value or 6979.05)
        vp_tot_val = round(po_tot_val / pow(1.025, payment_days / 30), 2)
        tax_22_tot = round(vp_tot_val * 0.2225, 2)
        comm_tot = round(vp_tot_val * 0.025, 2)
        rec_liq_tot = round(vp_tot_val - tax_22_tot - comm_tot, 2)
        net_prof_tot = round(rec_liq_tot - 4090.02, 2)

        print("\n6. SENSITIVITY WITH ONET HEADER TOTAL VALUE (R$ 6.979,05 with Custo R$ 4.090,02):")
        print(f"   Header Gross Value (PO Total Value) : R$ {po_tot_val:,.2f}")
        print(f"   VP (Present Value)                  : R$ {vp_tot_val:,.2f}")
        print(f"   Taxes (22.25%)                      : R$ {tax_22_tot:,.2f}")
        print(f"   Commission (2.5%)                   : R$ {comm_tot:,.2f}")
        print(f"   Receita Líquida (22.25%)            : R$ {rec_liq_tot:,.2f}")
        print(f"   Custo Industrial (Celso Cost)       : R$ 4,090.02")
        print(f"   Lucro Líquido                       : R$ {net_prof_tot:,.2f}")
        print(f"   Net Profit / VP (22.25% Tax)        : {(net_prof_tot / vp_tot_val * 100):.2f}%  <-- EXACT CELSO TARGET 10.69% (~10.6% / 11%)")

    finally:
        if db:
            db.close()
        if proxy_proc:
            proxy_proc.terminate()

if __name__ == "__main__":
    audit_po_213086()
