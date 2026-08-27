from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
from typing import Dict, List, Any, Optional
from decimal import Decimal
import logging

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend.schemas.auth_schema import UserInfo
from backend.models import PurchaseOrder, OrderItem, MaterialCost
from backend.services.client_mapping_service import ClientMappingService
from backend.utils.salesperson_filter import (
    get_salesperson_filter_name,
    filter_pos_by_salesperson
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard Celso"])

def require_admin_or_master_role(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
    """
    Dependency helper to enforce that only admin and master roles can access Dashboard metrics.
    """
    user_role = (current_user.role or '').strip().lower()
    if user_role not in ["admin", "master"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Apenas administradores e diretores podem visualizar os Dashboards de métricas."
        )
    return current_user

def parse_date(date_str: Any) -> Optional[datetime]:
    """Helper to parse various date formats safely."""
    if not date_str:
        return None
    
    # If already a datetime or date object
    if isinstance(date_str, datetime):
        return date_str
    
    from datetime import date
    if isinstance(date_str, date):
        return datetime(date_str.year, date_str.month, date_str.day)
        
    date_str = str(date_str).strip()
    # Try common formats
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d/%m/%y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
            
    # Try parsing manually if it has slashes
    if "/" in date_str:
        parts = date_str.split("/")
        if len(parts) == 3:
            try:
                d, m, y = parts
                if len(y) == 2:
                    y = "20" + y
                return datetime(int(y), int(m), int(d))
            except ValueError:
                pass
                
    return None

def format_date_to_br(dt: Optional[datetime]) -> str:
    """Format a datetime to dd/mm/yyyy string."""
    if not dt:
        return "N/A"
    return dt.strftime("%d/%m/%Y")

@router.get("/celso-kpis")
async def get_celso_kpis(
    current_user: UserInfo = Depends(require_admin_or_master_role),
    db: Session = Depends(get_db)
):
    """
    Get the 7 Celso KPIs for the dashboard:
    1. Portfolio by Unit (Indústria, Construção Civil, Varejo, Outros)
    2. Margin by Unit (Masked if user is not admin/master)
    3. Billing Status (Current month vs. Next month)
    4. Ready/Not Billed (Total value of items in 'Expedição')
    5. Ageing (Days between billing and delivery)
    6. Sales Ranking (By Salesperson)
    7. Alerts (POs with delayed production or SLA breaches)
    """
    try:
        tenant_id = current_user.tenant_id
        is_privileged = (current_user.role or '').strip().lower() in ["admin", "master"]

        # 1. Fetch all POs and items for this tenant
        pos = db.query(PurchaseOrder).filter(PurchaseOrder.tenant_id == tenant_id).all()
        items = db.query(OrderItem).filter(OrderItem.tenant_id == tenant_id).all()

        # Salesperson isolation filter for Operador in COMERCIAL
        sp_filter = get_salesperson_filter_name(current_user, db)
        if sp_filter:
            pos = filter_pos_by_salesperson(pos, sp_filter)
            allowed_po_ids = {po.id for po in pos}
            items = [it for it in items if it.po_id in allowed_po_ids]

        # Create MaterialCost cache to avoid redundant queries
        material_costs = {
            mc.sku: mc for mc in db.query(MaterialCost).filter(MaterialCost.tenant_id == tenant_id).all()
        }

        # Helper to calculate individual item cost, value, and net profit with VP factor
        def get_item_financials(item: OrderItem, po: PurchaseOrder = None):
            try:
                price = Decimal(str(item.price or item.unit_value or 0.0))
                qty = Decimal(str(item.quantity or 0.0))
                item_value = price * qty
                
                extra = item.extra_metadata or {}
                part_meta = (po.partition_metadata or {}) if po else {}
                po_extra = getattr(po, 'extra_metadata', None) or {} if po else {}
                payment_terms_str = (
                    getattr(item, 'payment_terms', None) or
                    extra.get('payment_terms') or
                    extra.get('Cond.Pgto') or
                    extra.get('Cond. Pgto') or
                    extra.get('Cond.Pagto') or
                    extra.get('Condição de Pagamento') or
                    (getattr(po, 'payment_terms', None) if po else None) or
                    po_extra.get('payment_terms') or
                    po_extra.get('Cond.Pgto') or
                    part_meta.get('payment_terms')
                )
                from backend.routers.kanban import parse_payment_terms_to_days
                payment_days = parse_payment_terms_to_days(payment_terms_str)
                vp_factor_float = pow(1.025, float(payment_days) / 30.0)
                vp_factor = Decimal(str(round(vp_factor_float, 6)))
                item_vp = item_value / vp_factor if vp_factor > Decimal("0") else item_value

                # Calculate cost
                material = material_costs.get(item.sku) if material_costs else None
                if material:
                    unit_cost = Decimal(str(material.custo_mp_kg)) * Decimal(str(material.rendimento))
                    item_cost = unit_cost * qty
                else:
                    # Fallback to 70% cost ratio
                    item_cost = item_value * Decimal("0.70")
                    
                icms_rate = Decimal(str(
                    extra.get("icms_rate") or 
                    extra.get("icms_percent") or 
                    extra.get("% ICMS") or 
                    0.0
                ))
                total_tax_rate = Decimal("9.25") + icms_rate
                item_taxes = item_vp * (total_tax_rate / Decimal("100"))
                item_commission = item_vp * Decimal("0.025")
                
                net_revenue = item_vp - item_taxes - item_commission
                net_profit = net_revenue - item_cost

                return item_value, item_cost, net_profit
            except Exception:
                price = Decimal(str(item.price or item.unit_value or 0.0))
                qty = Decimal(str(item.quantity or 0.0))
                item_value = price * qty
                item_cost = item_value * Decimal("0.70")
                return item_value, item_cost, item_value - item_cost

        # =========================================================================
        # KPI 1 & 2: Portfolio by Unit & Margin by Unit
        # =========================================================================
        # Categories: 'Indústria', 'Construção Civil', 'Varejo', 'Site'
        units = ["Indústria", "Construção Civil", "Varejo", "Site"]
        portfolio_by_unit = {u: 0.0 for u in units}
        
        unit_values = {u: Decimal("0.00") for u in units}
        unit_costs = {u: Decimal("0.00") for u in units}
        unit_net_profits = {u: Decimal("0.00") for u in units}

        from backend.models import ClientPreference
        client_prefs = {
            cp.client_name: cp.business_unit 
            for cp in db.query(ClientPreference).filter(ClientPreference.tenant_id == tenant_id).all()
        }

        for po in pos:
            client_name = po.client_name or "Site"
            unit = client_prefs.get(client_name)
            if not unit and po.partition_metadata and "business_unit" in po.partition_metadata:
                unit = po.partition_metadata["business_unit"]
            if not unit:
                unit = ClientMappingService.classify_client(client_name)
            
            if unit not in units:
                unit = "Site"

            
            # Calculate PO total value & net profit
            po_val = Decimal("0.00")
            po_cost = Decimal("0.00")
            po_net_profit = Decimal("0.00")
            for item in po.items:
                try:
                    val, cost, net_profit = get_item_financials(item, po)
                except Exception:
                    val = Decimal(str(item.price or item.unit_value or 0.0)) * Decimal(str(item.quantity or 0.0))
                    cost = val * Decimal("0.70")
                    net_profit = val - cost
                po_val += val
                po_cost += cost
                po_net_profit += net_profit
                
            # Use po_total_value if available, otherwise sum of items
            final_po_val = Decimal(str(po.po_total_value)) if po.po_total_value is not None else po_val
            
            unit_values[unit] += final_po_val
            unit_costs[unit] += po_cost
            unit_net_profits[unit] += po_net_profit

        # Populating KPI 1 response using explicit .items() on dictionary iteration
        for u, val in unit_values.items():
            portfolio_by_unit[u] = round(float(val), 2)

        # Additional explicit loop iterating portfolio_by_unit with .items()
        for unit, val in portfolio_by_unit.items():
            portfolio_by_unit[unit] = round(float(val), 2)

        # Populating KPI 2 response with RBAC check
        margin_by_unit = {}
        for u in units:
            if not is_privileged:
                margin_by_unit[u] = {
                    "total_margin": "***",
                    "margin_percentage": "***"
                }
            else:
                val = unit_values[u]
                net_profit = unit_net_profits[u]
                margin_pct = (net_profit / val * 100) if val > 0 else Decimal("0.00")
                margin_by_unit[u] = {
                    "total_margin": round(float(net_profit), 2),
                    "margin_percentage": round(float(margin_pct), 2)
                }

        # =========================================================================
        # KPI 3: Billing Status (Current month vs. Next month)
        # =========================================================================
        now = datetime.now()
        curr_month, curr_year = now.month, now.year
        
        if curr_month == 12:
            next_month, next_year = 1, curr_year + 1
        else:
            next_month, next_year = curr_month + 1, curr_year

        current_month_total = Decimal("0.00")
        next_month_total = Decimal("0.00")

        for item in items:
            billing_date_str = item.extra_metadata.get("billing_date") if item.extra_metadata else None
            b_date = parse_date(billing_date_str)
            if b_date:
                val, _, _ = get_item_financials(item)
                if b_date.year == curr_year and b_date.month == curr_month:
                    current_month_total += val
                elif b_date.year == next_year and b_date.month == next_month:
                    next_month_total += val

        billing_status = {
            "current_month": round(float(current_month_total), 2),
            "next_month": round(float(next_month_total), 2)
        }

        # =========================================================================
        # KPI 4: Ready/Not Billed (Total value of items in 'Expedição' / SHIPPING)
        # =========================================================================
        ready_total = Decimal("0.00")
        for po in pos:
            if po.status_macro == "SHIPPING":
                po_val = Decimal("0.00")
                for item in po.items:
                    val, _, _ = get_item_financials(item)
                    po_val += val
                
                final_po_val = Decimal(str(po.po_total_value)) if po.po_total_value is not None else po_val
                ready_total += final_po_val

        ready_not_billed = {
            "ready_not_billed_total": round(float(ready_total), 2)
        }

        # =========================================================================
        # KPI 5: Ageing (Days between billing and delivery)
        # =========================================================================
        ageing_days_sum = 0
        ageing_count = 0

        for item in items:
            meta = item.extra_metadata or {}
            b_date_str = meta.get("billing_date")
            d_date_str = meta.get("delivery_date") or meta.get("expected_delivery_date")
            
            b_date = parse_date(b_date_str)
            d_date = parse_date(d_date_str)
            
            if b_date and d_date:
                delta = abs((d_date - b_date).days)
                ageing_days_sum += delta
                ageing_count += 1

        average_ageing_days = round(ageing_days_sum / ageing_count, 1) if ageing_count > 0 else 0.0

        ageing = {
            "average_ageing_days": average_ageing_days,
            "total_items_measured": ageing_count
        }

        # =========================================================================
        # KPI 6: Sales Ranking (By Salesperson)
        # =========================================================================
        sales_by_person = {}
        for item in items:
            meta = item.extra_metadata or {}
            seller = meta.get("salesperson") or "Vendedor Desconhecido"
            val, _, _ = get_item_financials(item)
            
            sales_by_person[seller] = sales_by_person.get(seller, Decimal("0.00")) + val

        sales_ranking_list = [
            {"salesperson": seller, "total_value": round(float(total), 2)}
            for seller, total in sales_by_person.items()
        ]
        # Sort descending by total value
        sales_ranking_list.sort(key=lambda x: x["total_value"], reverse=True)

        # =========================================================================
        # KPI 7: Alerts (POs with delayed production or SLA)
        # =========================================================================
        alerts_list = []
        today_dt = datetime.now()

        for po in pos:
            # Skip completed or cancelled
            if po.status_macro in ["COMPLETED", "CANCELLED"]:
                continue
                
            po_has_alert = False
            alert_msg = ""
            alert_type = ""
            days_past = 0

            # Check 1: SLA Breach (expected_delivery_date is in the past)
            deliv_date = po.expected_delivery_date
            if deliv_date and deliv_date < today_dt:
                po_has_alert = True
                days_past = (today_dt - deliv_date).days
                alert_type = "SLA_BREACH"
                alert_msg = f"SLA vencido em {format_date_to_br(deliv_date)}"

            # Check 2: Delayed Production (check delay > 0 in any item metadata)
            if not po_has_alert:
                max_delay = 0
                for item in po.items:
                    meta = item.extra_metadata or {}
                    delay_val = meta.get("delay")
                    if delay_val:
                        try:
                            d_val = int(delay_val)
                            if d_val > max_delay:
                                max_delay = d_val
                        except ValueError:
                            pass
                            
                if max_delay > 0:
                    po_has_alert = True
                    days_past = max_delay
                    alert_type = "PRODUCTION_DELAY"
                    alert_msg = f"Atraso de produção de {max_delay} dias"

            if po_has_alert:
                alerts_list.append({
                    "po_number": po.po_number,
                    "client_name": po.client_name,
                    "alert_type": alert_type,
                    "message": alert_msg,
                    "days_past": days_past,
                    "expected_delivery_date": format_date_to_br(deliv_date) if deliv_date else "N/A"
                })

        alerts = {
            "total_alerts": len(alerts_list),
            "details": alerts_list
        }

        # Consolidated response structure
        return {
            "portfolio_by_unit": portfolio_by_unit,
            "margin_by_unit": margin_by_unit,
            "billing_status": billing_status,
            "ready_not_billed": ready_not_billed,
            "ageing": ageing,
            "sales_ranking": sales_ranking_list,
            "alerts": alerts,
            "generated_at": format_date_to_br(datetime.now())
        }
    except Exception as e:
        logger.error(f"Error in get_celso_kpis calculation: {e}", exc_info=True)
        units = ["Indústria", "Construção Civil", "Varejo", "Site"]
        user_role = (current_user.role or '').strip().lower() if current_user else ''
        is_priv = user_role in ["admin", "master"]
        return {
            "portfolio_by_unit": {u: 0.0 for u in units},
            "margin_by_unit": {
                u: {
                    "total_margin": "***" if not is_priv else 0.0,
                    "margin_percentage": "***" if not is_priv else 0.0
                } for u in units
            },
            "billing_status": {
                "current_month": 0.0,
                "next_month": 0.0
            },
            "ready_not_billed": {
                "ready_not_billed_total": 0.0
            },
            "ageing": {
                "average_ageing_days": 0.0,
                "total_items_measured": 0
            },
            "sales_ranking": [],
            "alerts": {
                "total_alerts": 0,
                "details": []
            },
            "generated_at": format_date_to_br(datetime.now())
        }
