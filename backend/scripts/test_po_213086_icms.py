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

def test_po_213086_icms():
    proxy_proc = ensure_cloud_sql_proxy()
    db = None
    try:
        from backend.database import SessionLocal
        from backend.models import PurchaseOrder, OrderItem, MaterialCost

        db = SessionLocal()
        print("\n" + "="*80)
        print("PRE-DEPLOY VERIFICATION: DYNAMIC ICMS MARGIN TEST ON PO 213086")
        print("="*80)

        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == "213086").first()
        if not po:
            print("[ERROR] PO 213086 not found in DB.")
            return

        print("\n1. PURCHASE ORDER HEADERS:")
        print(f"   PO Number       : {po.po_number}")
        print(f"   Client Name     : {po.client_name}")
        print(f"   Status Macro    : {po.status_macro}")
        print(f"   PO Total Value  : R$ {float(po.po_total_value or 0):,.2f}")

        total_gross = 0.0
        total_vp = 0.0
        total_taxes = 0.0
        total_commission = 0.0
        total_freight = 0.0
        total_costs = 0.0
        weighted_icms_sum = 0.0

        print("\n2. ORDER ITEMS & DYNAMIC ICMS BREAKDOWN:")
        for idx, item in enumerate(po.items, 1):
            qty = float(item.quantity)
            price = float(item.price)
            item_gross = qty * price
            extra = item.extra_metadata or {}
            
            # Lookup material cost
            mat = db.query(MaterialCost).filter(MaterialCost.sku == item.sku).first()
            if not mat:
                mat = db.query(MaterialCost).filter(MaterialCost.sku.ilike(f"%{item.sku}%")).first()
            
            unit_cost = (float(mat.custo_mp_kg) * float(mat.rendimento)) if mat else float(extra.get('unit_cost') or 0)
            item_cost = qty * unit_cost

            # Read raw ONET % ICMS rate
            raw_icms_rate = float(
                extra.get('icms_rate') or 
                extra.get('icms_percent') or 
                extra.get('% ICMS') or 
                0.0
            )

            # Total dynamic tax rate = 9.25% PIS/COFINS + Item's ICMS %
            item_tax_rate = 9.25 + raw_icms_rate

            payment_terms = extra.get('payment_terms') or '28/35/42'
            payment_days = parse_payment_terms_to_days(payment_terms)
            vp_factor = pow(1.025, payment_days / 30)
            item_vp = item_gross / vp_factor

            item_taxes = item_vp * (item_tax_rate / 100.0)
            item_commission = item_vp * 0.025
            item_freight = float(extra.get('freight') or 0.0)

            total_gross += item_gross
            total_vp += item_vp
            total_taxes += item_taxes
            total_commission += item_commission
            total_freight += item_freight
            total_costs += item_cost
            weighted_icms_sum += (raw_icms_rate * item_gross)

            print(f"   Item #{idx}:")
            print(f"     SKU             : {item.sku}")
            print(f"     Description     : {extra.get('description') or 'Filme De Protecao'}")
            print(f"     Quantity        : {qty} KG")
            print(f"     Unit Price      : R$ {price:,.2f}")
            print(f"     Item Gross Total: R$ {item_gross:,.2f}")
            print(f"     Payment Terms   : '{payment_terms}' -> {payment_days:.1f} avg days")
            print(f"     Raw % ICMS Meta : {raw_icms_rate:.2f}%")
            print(f"     Dynamic Tax Rate: {item_tax_rate:.2f}%  (9.25% PIS/COFINS + {raw_icms_rate:.2f}% ICMS)")
            print(f"     Unit Cost       : R$ {unit_cost:,.4f}")
            print(f"     Total Cost Item : R$ {item_cost:,.2f}")

        vp_discount = total_gross - total_vp
        absolute_margin = total_vp - total_taxes - total_commission - total_freight
        net_profit = absolute_margin - total_costs

        margin_ratio = net_profit / (total_gross if total_gross > 0 else 1.0)
        margin_percentage = round(margin_ratio * 100.0, 2)
        avg_icms_rate = round(weighted_icms_sum / total_gross, 2) if total_gross > 0 else 0.0

        badge_color = 'RED'
        if margin_percentage >= 30:
            badge_color = 'GREEN'
        elif margin_percentage >= 19:
            badge_color = 'YELLOW'
        elif margin_percentage >= 10:
            badge_color = 'ORANGE'

        print("\n3. DYNAMIC ICMS FORMULA STEP-BY-STEP CALCULATION TRACE:")
        print(f"   PIS/COFINS Baseline Rate : 9.25%")
        print(f"   ONET Raw % ICMS Rate     : {avg_icms_rate:.2f}%")
        print(f"   Total Dynamic Tax Rate   : {(9.25 + avg_icms_rate):.2f}%  (9.25% + {avg_icms_rate:.2f}%)")
        print(f"   ------------------------------------------------------------")
        print(f"   (+) Preço Total (Bruto)  : R$ {total_gross:,.2f}")
        print(f"   (-) Ajuste VP (Prazo)    : R$ -{vp_discount:,.2f}")
        print(f"   (=) Valor Presente (VP)  : R$ {total_vp:,.2f}")
        print(f"   (-) Impostos Dinâmicos  : R$ -{total_taxes:,.2f}  ({(9.25 + avg_icms_rate):.2f}% of VP)")
        print(f"   (-) Comissão (2.5%)      : R$ -{total_commission:,.2f}")
        print(f"   (-) Frete                : R$ -{total_freight:,.2f}")
        print(f"   ------------------------------------------------------------")
        print(f"   (=) Receita Líquida      : R$ {absolute_margin:,.2f}")
        print(f"   (-) Custo Industrial     : R$ -{total_costs:,.2f}")
        print(f"   ------------------------------------------------------------")
        print(f"   (=) Lucro Líquido        : R$ {net_profit:,.2f}")
        print(f"   ------------------------------------------------------------")
        print(f"   Margem Final (%)         : {margin_percentage:.2f}%  (Lucro Líquido / Gross Revenue * 100)")
        print(f"   Badge Color              : {badge_color}")

        print("\n4. MANDATORY AUDIT OUTPUT TABLE:")
        print("   +---------------------------------------+-----------------+")
        print("   | Step / Metric                         | Value (R$) / %  |")
        print("   +---------------------------------------+-----------------+")
        print(f"   | Valor Bruto (Preço Total)             | R$ {total_gross:>12,.2f} |")
        print(f"   | Ajuste VP (35 dias médio)             | R$ -{vp_discount:>11,.2f} |")
        print(f"   | Valor Presente (VP)                   | R$ {total_vp:>12,.2f} |")
        print(f"   | Impostos (9.25% PIS/COFINS + {avg_icms_rate:.0f}% ICMS) | R$ -{total_taxes:>11,.2f} |")
        print(f"   | Comissão (2.5%)                       | R$ -{total_commission:>11,.2f} |")
        print(f"   | Receita Líquida                       | R$ {absolute_margin:>12,.2f} |")
        print(f"   | Custo Industrial                      | R$ -{total_costs:>11,.2f} |")
        print(f"   | Lucro Líquido                         | R$ {net_profit:>12,.2f} |")
        print(f"   | Margem Final (%)                      | {margin_percentage:>14.2f}% |")
        print("   +---------------------------------------+-----------------+")

    finally:
        if db:
            db.close()
        if proxy_proc:
            proxy_proc.terminate()

if __name__ == "__main__":
    test_po_213086_icms()
