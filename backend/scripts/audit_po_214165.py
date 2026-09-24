import sys
import os
import socket
import subprocess
import time
import json
from decimal import Decimal
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

def audit_po_214165():
    proxy_proc = ensure_cloud_sql_proxy()
    db = None
    try:
        from backend.database import SessionLocal
        from backend.models import PurchaseOrder, OrderItem, MaterialCost
        from backend.routers.kanban import calculate_unit_aware_item_cost

        db = SessionLocal()
        po_num = "214165"
        
        print("=" * 100)
        print(f"FINANCIAL AUDIT TRACE FOR PO {po_num}")
        print("=" * 100)

        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number.ilike(f"%{po_num}%")).first()
        if not po:
            print(f"[ERROR] PO {po_num} not found in database.")
            return

        print(f"PO ID: {po.id}")
        print(f"PO Number: {po.po_number}")
        print(f"Client Name: {po.client_name}")
        print(f"Status Macro: {po.status_macro}")
        print(f"Partition Metadata: {json.dumps(po.partition_metadata or {}, indent=2, default=str)}")
        print("-" * 100)

        total_po_revenue = Decimal("0.00")
        total_po_cost = Decimal("0.00")

        for idx, item in enumerate(po.items, 1):
            extra = item.extra_metadata or {}
            sku = item.sku
            qty = Decimal(str(getattr(item, 'quantity', 0) or extra.get('quantity') or extra.get('quantidade') or 0))
            width = Decimal(str(getattr(item, 'width', 0) or extra.get('width') or extra.get('largura') or extra.get('Largura (mm)') or 0))
            length = Decimal(str(getattr(item, 'length', 0) or extra.get('length') or extra.get('comprimento') or extra.get('Comprimento (m)') or 0))
            unit_price = Decimal(str(getattr(item, 'unit_price', 0) or extra.get('unit_price') or extra.get('valor_unitario') or extra.get('Preco Unit.') or 0))
            item_total_val = Decimal(str(getattr(item, 'item_total_value', 0) or extra.get('item_total_value') or extra.get('valor_total') or extra.get('Vlr Total') or 0))
            
            if item_total_val <= Decimal("0") and qty > Decimal("0") and unit_price > Decimal("0"):
                item_total_val = qty * unit_price

            unit_str = str(getattr(item, 'unidade_medida', None) or extra.get('unidade_medida') or extra.get('unit') or extra.get('Un. Med.') or 'M2').upper().strip()

            print(f"\n--- ORDER ITEM #{idx} (SKU: {sku}) ---")
            print(f"  Description: {extra.get('description') or extra.get('desc_item') or 'N/A'}")
            print(f"  Unidade Medida: {unit_str}")
            print(f"  Quantity: {qty}")
            print(f"  Width (mm): {width}")
            print(f"  Length (m): {length}")
            print(f"  Unit Price (R$): {unit_price}")
            print(f"  Total Item Revenue (R$): {item_total_val}")
            print(f"  Extra Metadata: {json.dumps(extra, indent=2, default=str)}")

            # Fetch MaterialCost
            skus_to_check = [sku, sku.replace('.', ''), f"{sku}.0", f"0{sku}"]
            material = db.query(MaterialCost).filter(
                MaterialCost.tenant_id == po.tenant_id,
                MaterialCost.sku.in_(skus_to_check)
            ).first()

            if not material:
                material = db.query(MaterialCost).filter(MaterialCost.sku.in_(skus_to_check)).first()

            print(f"\n  --- MATERIAL COST TABLE RECORD FOR SKU '{sku}' ---")
            if material:
                cost_m2 = Decimal(str(material.custo_mp_kg or 0))
                rendimento = Decimal(str(material.rendimento or 1))
                impostos = Decimal(str(material.indice_impostos or 22.25))
                print(f"    Matched SKU in DB: {material.sku}")
                print(f"    Nome: {material.nome}")
                print(f"    Custo MP (R$/m2): {cost_m2}")
                print(f"    Rendimento (m2/kg): {rendimento}")
                print(f"    Indice Impostos (%): {impostos}")
            else:
                cost_m2 = Decimal(str(extra.get('custo_mp_kg') or extra.get('cost_mp') or 0))
                rendimento = Decimal(str(extra.get('rendimento') or 1))
                impostos = Decimal(str(extra.get('indice_impostos') or 22.25))
                print(f"    [WARNING] No record in material_costs table for SKU '{sku}'. Using extra_metadata values.")
                print(f"    Custo MP (R$/m2): {cost_m2}")
                print(f"    Rendimento (m2/kg): {rendimento}")
                print(f"    Indice Impostos (%): {impostos}")

            # Step-by-Step Calculation Trace
            total_item_cost, unit_cost = calculate_unit_aware_item_cost(item, material)
            
            print(f"\n  --- CALCULATION TRACE (Unit: '{unit_str}') ---")
            if unit_str in ('RL', 'UN'):
                width_m = width / Decimal("1000.0")
                total_area_m2 = width_m * length * qty if (width_m > 0 and length > 0) else qty
                print(f"    Width in meters: {width} mm / 1000 = {width_m} m")
                print(f"    Length in meters: {length} m")
                print(f"    Quantity: {qty} {unit_str}")
                print(f"    Total Area (m2): {width_m} m * {length} m * {qty} = {total_area_m2} m2")
                print(f"    Industrial Cost Formula: total_area_m2 * cost_per_m2")
                print(f"    Industrial Cost Computation: {total_area_m2} m2 * R$ {cost_m2}/m2 = R$ {total_item_cost:.2f}")
            elif unit_str == 'KG':
                cost_per_kg = cost_m2 * rendimento
                print(f"    Yield (m2/kg): {rendimento}")
                print(f"    Cost per kg: R$ {cost_m2}/m2 * {rendimento} m2/kg = R$ {cost_per_kg:.2f}/kg")
                print(f"    Industrial Cost Computation: {qty} kg * R$ {cost_per_kg:.2f}/kg = R$ {total_item_cost:.2f}")
            elif unit_str == 'M2':
                print(f"    Industrial Cost Computation: {qty} m2 * R$ {cost_m2}/m2 = R$ {total_item_cost:.2f}")
            else:
                print(f"    Fallback Cost Computation: {qty} * R$ {cost_m2} = R$ {total_item_cost:.2f}")

            print(f"    Calculated Total Industrial Item Cost: R$ {total_item_cost:.2f}")
            print(f"    Calculated Per-Unit Cost: R$ {unit_cost:.2f}")

            # Gross Margin Trace for Item
            tax_rate = impostos / Decimal("100.0")
            net_revenue = item_total_val * (Decimal("1.00") - tax_rate)
            gross_profit = net_revenue - total_item_cost
            item_margin = (gross_profit / item_total_val * Decimal("100.0")) if item_total_val > Decimal("0") else Decimal("0.00")

            print(f"\n  --- ITEM MARGIN BREAKDOWN ---")
            print(f"    Gross Item Revenue: R$ {item_total_val:.2f}")
            print(f"    Impostos ({impostos}%): -R$ {(item_total_val * tax_rate):.2f}")
            print(f"    Net Revenue (Receita Liquida): R$ {net_revenue:.2f}")
            print(f"    Total Industrial Cost: -R$ {total_item_cost:.2f}")
            print(f"    Gross Profit (Lucro Bruto): R$ {gross_profit:.2f}")
            print(f"    Item Gross Margin %: {item_margin:.2f}%")

            total_po_revenue += item_total_val
            total_po_cost += total_item_cost

        # Overall PO Margin Trace
        print("\n" + "=" * 100)
        print("OVERALL PO 214165 FINANCIAL SUMMARY & MARGIN TRACE")
        print("=" * 100)
        overall_impostos = Decimal("22.25") # default tax index
        overall_tax_rate = overall_impostos / Decimal("100.0")
        overall_net_revenue = total_po_revenue * (Decimal("1.00") - overall_tax_rate)
        overall_gross_profit = overall_net_revenue - total_po_cost
        overall_margin_pct = (overall_gross_profit / total_po_revenue * Decimal("100.0")) if total_po_revenue > Decimal("0") else Decimal("0.00")

        print(f"Total PO Gross Revenue: R$ {total_po_revenue:.2f}")
        print(f"Total Net Revenue (after {overall_impostos}% taxes): R$ {overall_net_revenue:.2f}")
        print(f"Total Industrial Cost: R$ {total_po_cost:.2f}")
        print(f"Total Gross Profit: R$ {overall_gross_profit:.2f}")
        print(f"FINAL PO GROSS MARGIN %: {overall_margin_pct:.2f}%")
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
    audit_po_214165()
