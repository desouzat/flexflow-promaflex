"""
FlexFlow Kanban Router
Endpoints for Kanban board operations and status management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status, File, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional, Any
from decimal import Decimal
from datetime import datetime
from pydantic import BaseModel, validator
import uuid

from backend.schemas.kanban_schema import (
    KanbanBoardResponse,
    KanbanColumn,
    POResponse,
    POItemResponse,
    MoveStatusRequest,
    MoveStatusResponse,
    POFilterParams,
    UpdateCommissionRequest,
    UpdateCommissionResponse,
    UpdateLogisticsChecklistRequest,
    UpdateLogisticsChecklistResponse,
    SlaJustificationRequest,
    SlaJustificationResponse,
)
from backend.schemas.auth_schema import UserInfo
from backend.database import get_db
from backend.routers.auth import get_current_user
from backend.models import PurchaseOrder, OrderItem, MaterialCost
from backend.utils.salesperson_filter import (
    get_salesperson_filter_name,
    filter_pos_by_salesperson,
    po_matches_salesperson
)

router = APIRouter(prefix="/api/kanban", tags=["Kanban"])


# Status mapping: Database status -> Display name (Portuguese)
# Standardized 6 Column Structure (FF-HARDENING-012.2: BILLING split from SHIPPING)
STATUS_DISPLAY_MAP = {
    "SUBMITTED": "Comercial",
    "APPROVED": "PCP",
    "MANUFACTURING": "Produção/Embalagem",
    "BILLING": "Faturamento",       # FF-HARDENING-012.2: new Faturamento stage
    "SHIPPING": "Expedição",        # FF-HARDENING-012.2: Expedição (was Faturamento/Expedição)
    "FINANCE": "Financeiro",
    
    # Legacy compatibility fallbacks
    "DRAFT": "Comercial",
    "WAITING_COMMERCIAL_PARTITION": "Comercial",
    "IN_PROGRESS": "Produção/Embalagem",
    "WAITING_DISPATCH": "Expedição",
    "AUDIT_PENDING": "Financeiro",
    "COMPLETED": "Financeiro",
    "ANALISE_CREDITO": "Financeiro",
    "CANCELLED": "Cancelado",
    "WAITING_MATERIAL": "PCP",
    "ARCHIVED_PARTITIONED": "Arquivado"
}

# Reverse mapping for API compatibility
DISPLAY_TO_DB_STATUS = {
    "Comercial": "SUBMITTED",
    "PCP": "APPROVED",
    "Produção/Embalagem": "MANUFACTURING",
    "Faturamento": "BILLING",          # FF-HARDENING-012.2
    "Expedição": "SHIPPING",           # FF-HARDENING-012.2
    # Legacy backward compat
    "Faturamento/Expedição": "BILLING", # old name now maps to Faturamento entry
    "Financeiro": "FINANCE",
    "Cancelado": "CANCELLED",
    "Arquivado": "ARCHIVED_PARTITIONED"
}

# Status flow for bidirectional movement - Standardized 6 Columns (FF-HARDENING-012.2)
STATUS_FLOW = {
    "SUBMITTED": {"next": "APPROVED", "prev": None},
    "APPROVED": {"next": "MANUFACTURING", "prev": "SUBMITTED"},
    "MANUFACTURING": {"next": "BILLING", "prev": "APPROVED"},   # FF-HARDENING-012.2
    "BILLING": {"next": "SHIPPING", "prev": "MANUFACTURING"},    # FF-HARDENING-012.2
    "SHIPPING": {"next": "ARCHIVED", "prev": "BILLING"},         # FF-HARDENING-012.2
    "FINANCE": {"next": "COMPLETED", "prev": "SHIPPING"},
    "COMPLETED": {"next": None, "prev": "FINANCE"},
    "ARCHIVED": {"next": None, "prev": "SHIPPING"},
    
    # Legacy flow fallbacks
    "DRAFT": {"next": "SUBMITTED", "prev": None},
    "WAITING_COMMERCIAL_PARTITION": {"next": "APPROVED", "prev": None},
    "IN_PROGRESS": {"next": "BILLING", "prev": "APPROVED"},
    "WAITING_DISPATCH": {"next": "FINANCE", "prev": "IN_PROGRESS"},
    "AUDIT_PENDING": {"next": "COMPLETED", "prev": "WAITING_DISPATCH"},
    "ANALISE_CREDITO": {"next": "COMPLETED", "prev": None},
    "WAITING_MATERIAL": {"next": "APPROVED", "prev": "SUBMITTED"},
    "ARCHIVED_PARTITIONED": {"next": None, "prev": None}
}


def _map_single_po(po: PurchaseOrder, db: Session, is_privileged: bool) -> POResponse:
    """Helper to serialize a single PurchaseOrder database model into a POResponse Pydantic schema."""
    from datetime import timedelta
    from backend.services.financial_service import FinancialService
    
    metrics = calculate_po_metrics(po)
    
    items = []
    for item in po.items:
        material = db.query(MaterialCost).filter(
            MaterialCost.tenant_id == po.tenant_id,
            MaterialCost.sku == item.sku
        ).first()
        
        unit_cost = Decimal("0.00")
        cost_meta = {}
        if material:
            unit_cost = Decimal(str(material.custo_mp_kg)) * Decimal(str(material.rendimento))
            cost_meta = {
                "total_cost": float(unit_cost),
                "cost_mp": float(unit_cost),
                "cost_updated_by": material.updated_by_user.name if material.updated_by_user else "Sistema",
                "cost_updated_at": material.updated_at.isoformat() if material.updated_at else None
            }
        
        item_extra = dict(item.extra_metadata or {})
        if cost_meta:
            item_extra.update(cost_meta)
            
        items.append(
            POItemResponse(
                id=str(item.id),
                sku=item.sku,
                quantity=item.quantity,
                price=Decimal(str(item.price)),
                                status_item=item.status_item,
                margin_item=(Decimal(str(item.price)) - unit_cost) if is_privileged else "***",
                total_cost=unit_cost,
                item_total_value=Decimal(str(item.item_total_value)) if item.item_total_value is not None else None,
                manual_commission_rate=Decimal(str(item.extra_metadata.get("manual_commission_rate"))) if item.extra_metadata and "manual_commission_rate" in item.extra_metadata else None,
                extra_metadata=item_extra,
                created_at=item.created_at,
                updated_at=item.updated_at
            )
        )
    
    commission_rate = None
    if po.partition_metadata and "manual_commission_rate" in po.partition_metadata:
        commission_rate = Decimal(str(po.partition_metadata["manual_commission_rate"]))
    else:
        commission_rate, _, _ = FinancialService.get_commission_rate(
            metrics["margin_percentage"],
            client_code=None,
            manual_override=None
        )
    
    commission_value = FinancialService.calculate_commission_value(
        metrics["total_value"],
        commission_rate
    )
    
    logistics_checklist = None
    if po.partition_metadata and "logistics_checklist" in po.partition_metadata:
        logistics_checklist = po.partition_metadata["logistics_checklist"]
    
    orig_delivery = None
    data_limite_val = None
    if po.partition_metadata and "expected_delivery_date" in po.partition_metadata:
        try:
            val = po.partition_metadata["expected_delivery_date"]
            if isinstance(val, str):
                orig_delivery = datetime.fromisoformat(val)
            elif isinstance(val, datetime):
                orig_delivery = val
        except Exception:
            pass
    if not orig_delivery:
        for item in po.items:
            if item.extra_metadata and "delivery_date" in item.extra_metadata:
                try:
                    val = item.extra_metadata["delivery_date"]
                    if isinstance(val, str):
                        if "/" in val:
                            d, m, y = val.split("/")
                            orig_delivery = datetime(int(y), int(m), int(d))
                        else:
                            orig_delivery = datetime.fromisoformat(val)
                    break
                except Exception:
                    pass
    if orig_delivery:
        data_limite_val = orig_delivery - timedelta(days=2)

    return POResponse(
        id=str(po.id),
        po_number=po.po_number,
        client_name=getattr(po, 'client_name', None) or "Cliente Desconhecido",
        supplier_name=getattr(po, 'client_name', None) or "Cliente Desconhecido",
        status_macro=po.status_macro,
        status=STATUS_DISPLAY_MAP.get(po.status_macro, po.status_macro),
        items=items,
        items_count=len(items),
        total_value=Decimal(str(po.po_total_value)) if po.po_total_value is not None else metrics["total_value"],
        margin_global=metrics["margin_global"] if is_privileged else "***",
        margin_percentage=metrics["margin_percentage"] if is_privileged else "***",
        commission_rate=commission_rate,
        commission_value=commission_value,
        shipping_cost=Decimal(str(po.shipping_cost)),
        expected_delivery_date=data_limite_val if data_limite_val else orig_delivery,
        delivery_date=orig_delivery,
        data_limite=data_limite_val,
        extra_metadata=po.partition_metadata,
        partition_metadata=po.partition_metadata,
        logistics_checklist=logistics_checklist,
        partition_reason=po.partition_reason,
        parent_po_id=str(po.parent_po_id) if po.parent_po_id else None,
        created_at=po.created_at,
        updated_at=po.updated_at,
        created_by=str(po.creator.id) if (po.creator and po.creator.id) else (str(po.created_by) if po.created_by else None),
        # SLA Justification fields (FF-HARDENING-006)
        sla_justification_category=po.sla_justification_category,
        sla_justification_text=po.sla_justification_text,
        sla_justification_user=po.sla_justification_user,
        sla_justification_at=po.sla_justification_at,
    )


def log_po_status_transition(
    db: Session,
    po: PurchaseOrder,
    from_status: Optional[str],
    to_status: str,
    current_user: UserInfo,
    justification: Optional[str] = None,
    is_exception: bool = False,
    extra_data: Optional[dict] = None
):
    print(f"DEBUG: Logging transition from {from_status} to {to_status}")
    """
    Log status transition for all items of a PO into the AuditLog using high-security V2 hashing (with tenant_id).
    """
    from backend.models import AuditLog, get_last_audit_hash
    from datetime import datetime
    import uuid
    
    timestamp = datetime.utcnow()
    changed_by_uuid = uuid.UUID(str(current_user.id)) if current_user.id else None
    
    for item in po.items:
        previous_hash = get_last_audit_hash(db, item.id)
        
        # Calculate new hash using V2
        audit_hash = AuditLog.calculate_hash_for_version(
            version=2,
            item_id=item.id,
            from_status=from_status,
            to_status=to_status,
            timestamp=timestamp,
            previous_hash=previous_hash,
            changed_by=changed_by_uuid,
            tenant_id=po.tenant_id
        )
        
        # Merge extra data
        log_extra = {
            "po_id": str(po.id),
            "po_number": po.po_number,
            "user_role": current_user.role
        }
        if extra_data:
            log_extra.update(extra_data)
            
        audit_entry = AuditLog(
            item_id=item.id,
            from_status=from_status,
            to_status=to_status,
            hash=audit_hash,
            previous_hash=previous_hash,
            is_exception=is_exception,
            justification=justification,
            changed_by=changed_by_uuid,
            extra_data=log_extra,
            hash_version=2
        )
        db.add(audit_entry)


def calculate_po_metrics(po: PurchaseOrder) -> dict:
    """Calculate metrics for a Purchase Order"""
    total_value = Decimal("0.00")
    total_cost = Decimal("0.00")
    
    for item in po.items:
        item_total = Decimal(str(item.price)) * item.quantity
        total_value += item_total
        # Assuming 70% cost ratio if no cost data available
        total_cost += item_total * Decimal("0.70")
    
    margin_global = total_value - total_cost
    margin_percentage = (margin_global / total_value * 100) if total_value > 0 else Decimal("0.00")
    
    return {
        "total_value": total_value,
        "margin_global": margin_global,
        "margin_percentage": margin_percentage
    }


@router.get("/board", response_model=KanbanBoardResponse)
async def get_kanban_board(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get complete Kanban board with all POs grouped by status.
    
    Returns POs organized in columns by their status, filtered by tenant.
    
    **Returns:**
    - Kanban board with columns for each status
    """
    
    is_privileged = current_user.role.lower() in ["admin", "master"]
    
    # Query database for POs
    pos = db.query(PurchaseOrder).filter(
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).all()
    
    # Salesperson isolation filter for Operador in COMERCIAL
    sp_filter = get_salesperson_filter_name(current_user, db)
    if sp_filter:
        pos = filter_pos_by_salesperson(pos, sp_filter)
    
    # Define status columns - FF-HARDENING-012.2: 6 Columns (Faturamento + Expedição split)
    # Comercial: SUBMITTED (fallback DRAFT, WAITING_COMMERCIAL_PARTITION)
    # PCP: APPROVED (fallback WAITING_MATERIAL)
    # Produção/Embalagem: MANUFACTURING (fallback IN_PROGRESS)
    # Faturamento: BILLING (new stage for NF-e emission)
    # Expedição: SHIPPING (fallback WAITING_DISPATCH) — checklist + uploads
    # Financeiro: FINANCE (fallback AUDIT_PENDING, ANALISE_CREDITO)
    status_columns = [
        ("Comercial", ["SUBMITTED", "DRAFT", "WAITING_COMMERCIAL_PARTITION"]),
        ("PCP", ["APPROVED", "WAITING_MATERIAL"]),
        ("Produção/Embalagem", ["MANUFACTURING", "IN_PROGRESS"]),
        ("Faturamento", ["BILLING"]),
        ("Expedição", ["SHIPPING", "WAITING_DISPATCH"]),
        ("Financeiro", ["FINANCE", "AUDIT_PENDING", "ANALISE_CREDITO"]),
        ("Concluídos", ["ARCHIVED", "ARCHIVED_PARTITIONED", "COMPLETED", "CANCELLED"])  # FF-HARDENING-013: cancelled cards render in Concluídos
    ]
    
    # Group POs by status
    columns = []
    for display_name, db_statuses in status_columns:
        # Filter POs for this column (may include multiple statuses), excluding child POs in WAITING_COMMERCIAL_PARTITION status to avoid duplicate board card rendering
        status_pos = [
            po for po in pos
            if po.status_macro in db_statuses and not (
                po.status_macro == "WAITING_COMMERCIAL_PARTITION" and po.parent_po_id is not None
            )
        ]
        
        # Convert to response models
        po_responses = []
        for po in status_pos:
            # Calculate metrics
            metrics = calculate_po_metrics(po)
            
            # Convert items resolving material costs
            items = []
            for item in po.items:
                # Query MaterialCost to find cost industrial
                material = db.query(MaterialCost).filter(
                    MaterialCost.tenant_id == po.tenant_id,
                    MaterialCost.sku == item.sku
                ).first()
                
                unit_cost = Decimal("0.00")
                cost_meta = {}
                if material:
                    unit_cost = Decimal(str(material.custo_mp_kg)) * Decimal(str(material.rendimento))
                    cost_meta = {
                        "total_cost": float(unit_cost),
                        "cost_mp": float(unit_cost),
                        "cost_updated_by": material.updated_by_user.name if material.updated_by_user else "Sistema",
                        "cost_updated_at": material.updated_at.isoformat() if material.updated_at else None
                    }
                
                item_extra = dict(item.extra_metadata or {})
                if cost_meta:
                    item_extra.update(cost_meta)
                    
                items.append(
                    POItemResponse(
                        id=str(item.id),
                        sku=item.sku,
                        quantity=item.quantity,
                        price=Decimal(str(item.price)),
                                                status_item=item.status_item,
                        margin_item=(Decimal(str(item.price)) - unit_cost) if is_privileged else "***",
                        total_cost=unit_cost,
                        item_total_value=Decimal(str(item.item_total_value)) if item.item_total_value is not None else None,
                        manual_commission_rate=Decimal(str(item.extra_metadata.get("manual_commission_rate"))) if item.extra_metadata and "manual_commission_rate" in item.extra_metadata else None,
                        extra_metadata=item_extra,
                        created_at=item.created_at,
                        updated_at=item.updated_at
                    )
                )
            
            # Get commission rate from metadata or calculate
            commission_rate = None
            commission_value = Decimal("0.00")
            if po.partition_metadata and "manual_commission_rate" in po.partition_metadata:
                commission_rate = Decimal(str(po.partition_metadata["manual_commission_rate"]))
            else:
                # Use default commission calculation
                from backend.services.financial_service import FinancialService
                commission_rate, _, _ = FinancialService.get_commission_rate(
                    metrics["margin_percentage"],
                    client_code=None,
                    manual_override=None
                )
            
            commission_value = FinancialService.calculate_commission_value(
                metrics["total_value"],
                commission_rate
            )
            
            # Get logistics checklist
            logistics_checklist = None
            if po.partition_metadata and "logistics_checklist" in po.partition_metadata:
                logistics_checklist = po.partition_metadata["logistics_checklist"]
            
            # Calculate original delivery date and data_limite
            from datetime import timedelta
            orig_delivery = None
            data_limite_val = None
            if po.partition_metadata and "expected_delivery_date" in po.partition_metadata:
                try:
                    val = po.partition_metadata["expected_delivery_date"]
                    if isinstance(val, str):
                        orig_delivery = datetime.fromisoformat(val)
                    elif isinstance(val, datetime):
                        orig_delivery = val
                except Exception:
                    pass
            if not orig_delivery:
                for item in po.items:
                    if item.extra_metadata and "delivery_date" in item.extra_metadata:
                        try:
                            val = item.extra_metadata["delivery_date"]
                            if isinstance(val, str):
                                if "/" in val:
                                    d, m, y = val.split("/")
                                    orig_delivery = datetime(int(y), int(m), int(d))
                                else:
                                    orig_delivery = datetime.fromisoformat(val)
                            break
                        except Exception:
                            pass
            if orig_delivery:
                data_limite_val = orig_delivery - timedelta(days=2)

            po_response = POResponse(
                id=str(po.id),
                po_number=po.po_number,
                client_name=getattr(po, 'client_name', None) or "Cliente Desconhecido",
                supplier_name=getattr(po, 'client_name', None) or "Cliente Desconhecido",
                status_macro=po.status_macro,  # Raw database status macro (e.g. 'APPROVED' for PCP)
                status=display_name,  # Alias for frontend compatibility
                items=items,
                items_count=len(items),
                total_value=Decimal(str(po.po_total_value)) if po.po_total_value is not None else metrics["total_value"],
                margin_global=metrics["margin_global"] if is_privileged else "***",
                margin_percentage=metrics["margin_percentage"] if is_privileged else "***",
                commission_rate=commission_rate,
                commission_value=commission_value,
                shipping_cost=Decimal(str(po.shipping_cost)),
                expected_delivery_date=data_limite_val if data_limite_val else orig_delivery,
                delivery_date=orig_delivery,
                data_limite=data_limite_val,
                extra_metadata=po.partition_metadata,
                partition_metadata=po.partition_metadata,
                logistics_checklist=logistics_checklist,
                partition_reason=po.partition_reason,
                created_at=po.created_at,
                updated_at=po.updated_at,
                created_by=str(po.creator.id) if (po.creator and po.creator.id) else (str(po.created_by) if po.created_by else None)
            )
            po_responses.append(po_response)
        
        column = KanbanColumn(
            status=display_name,  # Use display name
            count=len(po_responses),
            pos=po_responses
        )
        columns.append(column)
    
    return KanbanBoardResponse(
        columns=columns,
        total_pos=len(pos),
        tenant_id=str(current_user.tenant_id)
    )


@router.get("/pos", response_model=List[POResponse])
async def list_purchase_orders(
    status: Optional[str] = Query(None, description="Filter by status"),
    client_name: Optional[str] = Query(None, description="Filter by client name"),
    po_number: Optional[str] = Query(None, description="Filter by PO number"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List Purchase Orders with optional filters.
    
    **Query Parameters:**
    - **status**: Filter by PO status
    - **client_name**: Filter by client name (partial match)
    - **po_number**: Filter by PO number (partial match)
    - **skip**: Pagination offset
    - **limit**: Maximum number of results
    
    **Returns:**
    - List of Purchase Orders
    """
    
    # Query database
    query = db.query(PurchaseOrder).filter(
        PurchaseOrder.tenant_id == current_user.tenant_id
    )
    
    # Apply filters
    if status:
        # Convert display name to DB status if needed
        db_status = DISPLAY_TO_DB_STATUS.get(status, status)
        query = query.filter(PurchaseOrder.status_macro == db_status)
    
    if po_number:
        query = query.filter(PurchaseOrder.po_number.ilike(f"%{po_number}%"))
    
    # Apply pagination
    is_privileged = current_user.role.lower() in ["admin", "master"]
    pos = query.offset(skip).limit(limit).all()

    # Salesperson isolation filter for Operador in COMERCIAL
    sp_filter = get_salesperson_filter_name(current_user, db)
    if sp_filter:
        pos = filter_pos_by_salesperson(pos, sp_filter)
    
    # Convert to response models
    po_responses = []
    for po in pos:
        metrics = calculate_po_metrics(po)
        
        items = []
        for item in po.items:
            material = db.query(MaterialCost).filter(
                MaterialCost.tenant_id == po.tenant_id,
                MaterialCost.sku == item.sku
            ).first()
            unit_cost = Decimal("0.00")
            if material:
                unit_cost = Decimal(str(material.custo_mp_kg)) * Decimal(str(material.rendimento))
            
            items.append(
                POItemResponse(
                    id=str(item.id),
                    sku=item.sku,
                    quantity=item.quantity,
                    price=Decimal(str(item.price)),
                    status_item=item.status_item,
                    margin_item=(Decimal(str(item.price)) - unit_cost) if is_privileged else "***",
                    total_cost=unit_cost,
                    item_total_value=Decimal(str(item.item_total_value)) if item.item_total_value is not None else None,
                    manual_commission_rate=Decimal(str(item.extra_metadata.get("manual_commission_rate"))) if item.extra_metadata and "manual_commission_rate" in item.extra_metadata else None,
                    extra_metadata=item.extra_metadata,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
            )
        
        # Get commission rate
        commission_rate = None
        commission_value = Decimal("0.00")
        if po.partition_metadata and "manual_commission_rate" in po.partition_metadata:
            commission_rate = Decimal(str(po.partition_metadata["manual_commission_rate"]))
        else:
            from backend.services.financial_service import FinancialService
            commission_rate, _, _ = FinancialService.get_commission_rate(
                metrics["margin_percentage"],
                client_code=None,
                manual_override=None
            )
        
        commission_value = FinancialService.calculate_commission_value(
            metrics["total_value"],
            commission_rate
        )
        
        logistics_checklist = None
        if po.partition_metadata and "logistics_checklist" in po.partition_metadata:
            logistics_checklist = po.partition_metadata["logistics_checklist"]
        
        po_response = POResponse(
            id=str(po.id),
            po_number=po.po_number,
            client_name=getattr(po, 'client_name', None) or "Cliente Desconhecido",
            supplier_name=getattr(po, 'client_name', None) or "Cliente Desconhecido",
            status_macro=STATUS_DISPLAY_MAP.get(po.status_macro, po.status_macro),
            status=STATUS_DISPLAY_MAP.get(po.status_macro, po.status_macro),
            items=items,
            items_count=len(items),
            total_value=Decimal(str(po.po_total_value)) if po.po_total_value is not None else metrics["total_value"],
            margin_global=metrics["margin_global"] if is_privileged else "***",
            margin_percentage=metrics["margin_percentage"] if is_privileged else "***",
            commission_rate=commission_rate,
            commission_value=commission_value,
            shipping_cost=Decimal(str(po.shipping_cost)),
            expected_delivery_date=getattr(po, 'expected_delivery_date', None),
            extra_metadata=po.partition_metadata,
            partition_metadata=po.partition_metadata,
            logistics_checklist=logistics_checklist,
            partition_reason=po.partition_reason,
            parent_po_id=str(po.parent_po_id) if po.parent_po_id else None,
            created_at=po.created_at,
            updated_at=po.updated_at,
            created_by=str(po.creator.id) if (po.creator and po.creator.id) else (str(po.created_by) if po.created_by else None)
        )
        po_responses.append(po_response)
    
    return po_responses


@router.get("/pos/{po_id}", response_model=POResponse)
async def get_purchase_order(
    po_id: str,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific Purchase Order by ID.
    
    **Parameters:**
    - **po_id**: Purchase Order ID
    
    **Returns:**
    - Purchase Order details with items
    """
    
    import uuid
    try:
        uuid.UUID(po_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase Order {po_id} not found"
        )

    # Query database
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase Order {po_id} not found"
        )

    sp_filter = get_salesperson_filter_name(current_user, db)
    if sp_filter and not po_matches_salesperson(po, sp_filter):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase Order {po_id} not found"
        )
    
    is_privileged = current_user.role.lower() in ["admin", "master"]
    response_data = _map_single_po(po, db, is_privileged)
    print("\n================== BACKEND TRACEABILITY LOG ==================")
    print(f"PO Details Requested: {po_id}")
    print(f"Client Name: {response_data.client_name}")
    print(f"Expected Delivery Date: {response_data.expected_delivery_date}")
    print(f"JSON Output:\n{response_data.model_dump_json(indent=2)}")
    print("==============================================================\n")
    return response_data


@router.get("/pos/{po_id}/handoff-history")
async def get_handoff_history(
    po_id: str,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get handoff history and SLA analytics for a specific PO.
    """
    import uuid
    from backend.models import AuditLog, OrderItem
    from datetime import datetime
    
    try:
        uuid.UUID(po_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase Order {po_id} not found"
        )

    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase Order {po_id} not found"
        )
        
    # Reconstruct chronological traces joining OrderItem
    logs = db.query(AuditLog).join(OrderItem).filter(
        OrderItem.po_id == po.id
    ).order_by(AuditLog.created_at.asc()).all()
    
    # Deduplicate logs based on from_status, to_status, and date
    seen = set()
    unique_logs = []
    for log in logs:
        timestamp_str = log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else ""
        key = (log.from_status, log.to_status, timestamp_str)
        if key not in seen:
            seen.add(key)
            unique_logs.append(log)
    logs = unique_logs
        
    timeline = []
    initial_status = logs[0].from_status if (logs and logs[0].from_status) else "DRAFT"
    creator_name = "Sistema"
    if po.creator:
        creator_name = po.creator.name or po.creator.email
        
    timeline.append({
        "status": initial_status,
        "start": po.created_at,
        "user": creator_name
    })
    
    for log in logs:
        if timeline:
            timeline[-1]["end"] = log.created_at
        user_name = "Sistema"
        if log.changed_by_user:
            user_name = log.changed_by_user.name or log.changed_by_user.email
            
        timeline.append({
            "status": log.to_status,
            "start": log.created_at,
            "user": user_name
        })
        
    if timeline:
        timeline[-1]["end"] = None
        
    def get_area_name(status_db):
        status_db = status_db.upper() if status_db else ""
        if status_db in ["DRAFT", "SUBMITTED", "WAITING_COMMERCIAL_PARTITION"]:
            return "Comercial"
        elif status_db in ["APPROVED"]:
            return "PCP"
        elif status_db in ["IN_PROGRESS"]:
            return "Produção"
        elif status_db in ["WAITING_DISPATCH"]:
            return "Expedição"
        elif status_db in ["AUDIT_PENDING", "COMPLETED", "ANALISE_CREDITO"]:
            return "Financeiro"
        elif status_db in ["ARCHIVED"]:
            return "Arquivado"
        return "Comercial"
        
    grouped_areas = []
    current_area = None
    for interval in timeline:
        area_name = get_area_name(interval["status"])
        start_time = interval["start"]
        end_time = interval.get("end")
        user = interval["user"]
        
        if not current_area or current_area["area"] != area_name:
            if current_area:
                grouped_areas.append(current_area)
            current_area = {
                "area": area_name,
                "arrival": start_time,
                "departure": end_time,
                "users": [user]
            }
        else:
            current_area["departure"] = end_time
            if user not in current_area["users"]:
                current_area["users"].append(user)
                
    if current_area:
        grouped_areas.append(current_area)
        
    def to_naive(dt):
        if dt is None:
            return None
        return dt.replace(tzinfo=None) if dt.tzinfo else dt

    def to_brasilia(dt_naive):
        """Convert a UTC-naive datetime to America/Sao_Paulo (UTC-3) for display.
        FF-HARDENING-011 Item 1: All datetimes stored in DB are UTC.
        Brasília is UTC-3 (no DST in production calendar consideration needed here;
        the offset is applied as a fixed -3h shift consistent with Brazil Standard Time).
        This function is ONLY used for human-readable display strings, never for
        duration/business-hours arithmetic (which stays in UTC-naive).
        """
        if dt_naive is None:
            return None
        from datetime import timedelta
        return dt_naive + timedelta(hours=-3)

    now_naive = to_naive(datetime.utcnow())
    po_created_naive = to_naive(po.created_at)
    
    is_archived = (po.status_macro in ["ARCHIVED", "ARCHIVED_PARTITIONED"])
    if is_archived:
        # SLA timer stops at last archiving transition log
        last_transition_naive = to_naive(logs[-1].created_at) if logs else to_naive(po.updated_at)
        if not last_transition_naive:
            last_transition_naive = po_created_naive
        now_naive = last_transition_naive
        
    def format_duration(td):
        total_seconds = int(td.total_seconds())
        if total_seconds < 60:
            return "< 1m"
        days = total_seconds // 86400
        total_seconds %= 86400
        hours = total_seconds // 3600
        total_seconds %= 3600
        minutes = total_seconds // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or (days == 0 and hours == 0):
            parts.append(f"{minutes}m")
        return " ".join(parts)
        
    formatted_history = []
    for item in grouped_areas:
        arrival_naive = to_naive(item["arrival"])
        departure_naive = to_naive(item["departure"])
        end_for_duration = departure_naive if departure_naive else now_naive

        duration_td = end_for_duration - arrival_naive
        duration_str = format_duration(duration_td)

        # FF-HARDENING-011 [Item 1]: Convert UTC → Brasília (UTC-3) for display
        arrival_brt = to_brasilia(arrival_naive)
        departure_brt = to_brasilia(departure_naive)

        arrival_str = arrival_brt.strftime("%d/%m/%Y %H:%M") if arrival_brt else ""
        departure_str = departure_brt.strftime("%d/%m/%Y %H:%M") if departure_brt else ("Concluído" if is_archived else "Em andamento")

        formatted_history.append({
            "area": item["area"],
            "arrival": arrival_str,          # Brasília time (display)
            "arrival_utc_iso": arrival_naive.isoformat() if arrival_naive else None,  # UTC (for SLA math)
            "departure": departure_str,       # Brasília time (display)
            "duration": duration_str,
            "duration_seconds": int(duration_td.total_seconds()),
            "user": ", ".join(item["users"])
        })
        
    # Check is_replacement
    is_replacement = False
    if po.partition_metadata and po.partition_metadata.get("is_replacement"):
        is_replacement = True
    elif po.items:
        for item in po.items:
            if item.extra_metadata and item.extra_metadata.get("is_replacement"):
                is_replacement = True
                break
                
    # ── FF-HARDENING-010: Business-Hours SLA Calculation ─────────────────────
    # Load SLA config from GlobalConfig (falls back to safe defaults)
    from backend.utils.business_hours import get_sla_config_from_db, calculate_business_hours
    sla_config = get_sla_config_from_db(db, po.tenant_id)

    # SLA multiplier for replacement orders
    sla_factor = 0.5 if is_replacement else 1.0
    total_sla_hours = float(sla_config["sla_total_hours"]) * sla_factor

    # Area SLAs — scale default 24h-base by the configured sla_area_hours ratio
    # For now we keep the relative proportions between areas and scale them.
    area_sla_base = float(sla_config["sla_area_hours"])
    # Original proportions: Com=48, PCP=24, Prod=72, Exp=48, Fin=48 / base=48
    area_sla_ratios = {
        "Comercial":  48.0 / 48.0,
        "PCP":        24.0 / 48.0,
        "Produção":   72.0 / 48.0,
        "Expedição":  48.0 / 48.0,
        "Financeiro": 48.0 / 48.0,
        "Arquivado":   0.0,
    }
    area_slas = {k: v * area_sla_base for k, v in area_sla_ratios.items()}

    active_area = STATUS_DISPLAY_MAP.get(po.status_macro, "Comercial")
    current_area_sla_hours = area_slas.get(active_area, area_sla_base) * sla_factor

    # Total elapsed business hours from PO creation to now (or archive time)
    total_elapsed_hours = 0.0
    if po_created_naive and now_naive and now_naive > po_created_naive:
        total_elapsed_hours = calculate_business_hours(
            start_time=po_created_naive,
            end_time=now_naive,
            config=sla_config,
        )

    # Current area elapsed business hours (from latest handoff to now)
    current_area_elapsed_hours = 0.0
    if not is_archived and formatted_history:
        # Use the UTC ISO field stored alongside the BRT display string
        try:
            last_arrival_utc_iso = formatted_history[-1].get("arrival_utc_iso")
            if last_arrival_utc_iso:
                last_arrival_utc = datetime.fromisoformat(last_arrival_utc_iso)
                if now_naive > last_arrival_utc:
                    current_area_elapsed_hours = calculate_business_hours(
                        start_time=last_arrival_utc,
                        end_time=now_naive,
                        config=sla_config,
                    )
            else:
                # Fallback: use raw seconds
                current_area_elapsed_hours = formatted_history[-1]["duration_seconds"] / 3600.0
        except (ValueError, KeyError):
            # Fallback: use raw seconds from formatted_history
            current_area_elapsed_hours = formatted_history[-1]["duration_seconds"] / 3600.0
    # ── End FF-HARDENING-010 ──────────────────────────────────────────────────
        
    # Construct chronological transitions history
    transitions = []
    
    # Initial status transition (po creation)
    initial_area = STATUS_DISPLAY_MAP.get(initial_status, initial_status)
    initial_reason = "CONFERIDO"
    # FF-HARDENING-011 [Item 1]: Display creation date in Brasília time
    po_created_brt = to_brasilia(po_created_naive)
    transitions.append({
        "date": po_created_brt.strftime("%d/%m/%Y %H:%M") if po_created_brt else "",
        "user": creator_name,
        "from_to": f"Mesa Conf ➔ {initial_area}",
        "reason": initial_reason
    })
    
    # Standardize area names for Solutions Engineer mapping
    def get_std_area_name(area_str):
        if not area_str:
            return ""
        s = area_str.upper().strip()
        if "COMERCIAL" in s:
            return "COMERCIAL"
        if "PCP" in s:
            return "PCP"
        if "PRODUÇÃO" in s or "PRODUCAO" in s or "EMBALAGEM" in s:
            return "PRODUÇÃO"
        if "FATURAMENTO" in s or "EXPEDIÇÃO" in s or "EXPEDICAO" in s:
            return "FATURAMENTO"
        if "FINANCEIRO" in s or "FINANCE" in s:
            return "FINANCEIRO"
        return s

    # Subsequent movements
    for log in logs:
        log_user = "Sistema"
        if log.changed_by_user:
            log_user = log.changed_by_user.name or log.changed_by_user.email
            
        from_area = STATUS_DISPLAY_MAP.get(log.from_status, log.from_status) if log.from_status else "Comercial"
        to_area = STATUS_DISPLAY_MAP.get(log.to_status, log.to_status) if log.to_status != "ARCHIVED" else "Arquivado"
        
        std_from = get_std_area_name(from_area)
        std_to = get_std_area_name(to_area)
        
        # Apply the Solutions Engineer's Reason Map strictly:
        mapped_reason = None
        
        db_from = log.from_status
        db_to = log.to_status
        
        # Enforce strict labeling from the Go-Live Sprint specifications
        if log.justification == "CONFERIDO FRETE" or (log.extra_data and log.extra_data.get("action_type") == "ALLOCATE_FREIGHT_CHILD"):
            mapped_reason = "CONFERIDO FRETE"
        elif (db_from == "APPROVED" and db_to == "SUBMITTED") or (std_from == "PCP" and std_to == "COMERCIAL"):
            mapped_reason = "PARTICIONAMENTO"
        elif (db_from == "MANUFACTURING" and db_to == "APPROVED") or (std_from == "PRODUÇÃO" and std_to == "PCP"):
            mapped_reason = "VERIFICAR POSSIBILIDADES COM TIME DE NEGÓCIOS"
        elif (db_from == "SHIPPING" and db_to == "FINANCE") or (std_from == "FATURAMENTO" and std_to == "FINANCEIRO"):
            mapped_reason = "LIBERADO"
        elif (std_from == "MESA CONF" or "MESA" in std_from) and std_to == "COMERCIAL":
            mapped_reason = "CONFERIDO"
        elif std_from == "COMERCIAL" and std_to == "FINANCEIRO":
            mapped_reason = "ENVIO ANÁLISE DE CRÉDITO"
        
        # Force "CONFERIDO" for all forward transitions and eliminate "[Outros]" for standard movements.
        # EXCEPTION: If the stored justification is already "CONFERIDO (TROCA/DEVOLUÇÃO)", preserve it
        # exactly — do NOT overwrite with plain "CONFERIDO". This flag is written by advance_po_status
        # for exchange/return cards and must surface unchanged in the timeline UI.
        is_forward_transition = False
        if std_from == "COMERCIAL" and std_to == "PCP":
            is_forward_transition = True
        elif std_from == "PCP" and std_to == "PRODUÇÃO":
            is_forward_transition = True
        elif std_from == "PRODUÇÃO" and std_to == "FATURAMENTO":
            is_forward_transition = True
        elif std_from == "FATURAMENTO" and std_to in ["FINANCEIRO", "ARQUIVADO", "PCP"]:
            is_forward_transition = True
        elif std_from == "FINANCEIRO" and std_to == "ARQUIVADO":
            is_forward_transition = True

        EXCHANGE_LABEL = "CONFERIDO (TROCA/DEVOLU\u00c7\u00c3O)"
        if is_forward_transition:
            if mapped_reason != "CONFERIDO FRETE" and log.justification != EXCHANGE_LABEL:
                mapped_reason = "CONFERIDO"
            elif log.justification == EXCHANGE_LABEL:
                # Preserve the exchange/return label verbatim
                mapped_reason = EXCHANGE_LABEL

        if mapped_reason:
            reason = mapped_reason
        else:
            reason = log.justification or ""
            if log.extra_data:
                if log.extra_data.get("return_reason"):
                    reason = log.extra_data.get("return_reason")
                elif log.extra_data.get("partition_reason"):
                    reason = log.extra_data.get("partition_reason")
                elif log.extra_data.get("audit_comment"):
                    reason = log.extra_data.get("audit_comment")

        # Default to '[Outros]' if no specific mapping exists
        if not reason or reason.strip() in ["", "—", "-", "None", "null"]:
            if is_forward_transition or (std_from in ["COMERCIAL", "PCP", "PRODUÇÃO", "FATURAMENTO", "FINANCEIRO"] and std_to in ["COMERCIAL", "PCP", "PRODUÇÃO", "FATURAMENTO", "FINANCEIRO", "ARQUIVADO"]):
                reason = "CONFERIDO"
            else:
                reason = "[Outros]"
            
        # FF-HARDENING-011 [Item 1]: Transitions date displayed in Brasília time
        log_dt_naive = to_naive(log.created_at)
        log_dt_brt = to_brasilia(log_dt_naive)
        transitions.append({
            "date": log_dt_brt.strftime("%d/%m/%Y %H:%M") if log_dt_brt else "",
            "user": log_user,
            "from_to": f"{from_area} ➔ {to_area}",
            "reason": reason
        })
        
    return {
        "handoff_history": formatted_history,
        "transitions": transitions,
        "is_replacement": is_replacement,
        "total_sla_hours": total_sla_hours,
        "total_elapsed_hours": total_elapsed_hours,
        "current_area": active_area,
        "current_area_sla_hours": current_area_sla_hours,
        "current_area_elapsed_hours": current_area_elapsed_hours,
        "is_archived": is_archived,
        # FF-HARDENING-010: expose SLA config so the frontend can display limits
        "sla_config": {
            "sla_total_hours": sla_config["sla_total_hours"],
            "sla_area_hours": sla_config["sla_area_hours"],
            "sla_start_hour": sla_config["sla_start_hour"],
            "sla_end_hour": sla_config["sla_end_hour"],
            "sla_working_days": sla_config["sla_working_days"],
        },
    }


@router.put("/pos/{po_id}/area-fields")
async def update_po_area_fields(
    po_id: str,
    fields: dict,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Dynamically merge area-specific custom fields into partition_metadata.
    """
    import uuid
    
    try:
        uuid.UUID(po_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase Order {po_id} not found"
        )

    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase Order {po_id} not found"
        )
        
    if po.status_macro == "ARCHIVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é permitido editar um pedido arquivado."
        )
        
    if po.partition_metadata is None:
        po.partition_metadata = {}
        
    # Merge custom fields
    meta = dict(po.partition_metadata)
    meta.update(fields)
    po.partition_metadata = meta
    
    # Synchronize specific properties
    if "client_name" in fields:
        po.client_name = fields["client_name"]
    if "data_programada" in fields:
        po.expected_delivery_date = fields["data_programada"]
    elif "expected_delivery_date" in fields:
        po.expected_delivery_date = fields["expected_delivery_date"]
        
    # Special: if is_replacement is passed, sync it to items to keep them aligned
    if "is_replacement" in fields:
        is_rep_val = fields["is_replacement"]
        for item in po.items:
            if item.extra_metadata is None:
                item.extra_metadata = {}
            item_meta = dict(item.extra_metadata)
            item_meta["is_replacement"] = is_rep_val
            item.extra_metadata = item_meta
            
    po.updated_at = datetime.utcnow()
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(po, "partition_metadata")
    db.commit()
    db.refresh(po)
    
    return {
        "success": True,
        "partition_metadata": po.partition_metadata
    }


# ─── FF-HARDENING-013 Issue B: Per-SKU production metrics endpoint ──────────

class ItemProductionUpdate(BaseModel):
    """Per-item production metrics for a single SKU."""
    item_id: str
    status_producao: Optional[str] = None
    qtd_real_produzida: Optional[float] = None
    perda_tecnica: Optional[float] = None


class ProductionUpdateBody(BaseModel):
    """Body for the bulk per-SKU production update endpoint."""
    items: List[ItemProductionUpdate]


@router.post("/pos/{po_id}/production")
async def save_production_per_sku(
    po_id: str,
    body: ProductionUpdateBody,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    FF-HARDENING-013 [Issue B]: Save per-SKU production metrics.

    Receives an array of item updates and writes status_producao,
    qtd_real_produzida, and perda_tecnica into each OrderItem.extra_metadata.
    This keeps production data at the item level for fine-grained per-SKU
    reporting, rather than aggregating at the PO level.

    No schema migrations required — values are stored inside the existing
    OrderItem.extra_metadata JSONB column.
    """
    import uuid as _uuid
    try:
        _uuid.UUID(po_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Purchase Order {po_id} not found")

    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()

    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Purchase Order {po_id} not found")

    if po.status_macro in ("ARCHIVED", "ARCHIVED_PARTITIONED", "COMPLETED", "CANCELLED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é permitido editar produção de um pedido finalizado/cancelado."
        )

    from sqlalchemy.orm.attributes import flag_modified as _flag_modified_prod

    # Build a fast lookup of item_id → item ORM object
    item_map = {str(item.id): item for item in po.items}
    updated_items = []

    for update in body.items:
        item = item_map.get(update.item_id)
        if not item:
            continue  # skip unknown item IDs gracefully

        if item.extra_metadata is None:
            item.extra_metadata = {}

        item_meta = dict(item.extra_metadata)

        if update.status_producao is not None:
            item_meta["status_producao"] = update.status_producao
        if update.qtd_real_produzida is not None:
            item_meta["qtd_real_produzida"] = update.qtd_real_produzida
        if update.perda_tecnica is not None:
            item_meta["perda_tecnica"] = update.perda_tecnica

        item_meta["production_updated_at"] = datetime.utcnow().isoformat()
        item_meta["production_updated_by"] = current_user.name or current_user.email

        item.extra_metadata = item_meta
        _flag_modified_prod(item, "extra_metadata")
        item.updated_at = datetime.utcnow()

        updated_items.append({
            "item_id": str(item.id),
            "sku": item.sku,
            "extra_metadata": item_meta
        })

    po.updated_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "updated_count": len(updated_items),
        "items": updated_items
    }


# ─── FF-HARDENING-012.1: Cancel PO endpoint ───────────────────────────────
class CancelPORequest(BaseModel):
    justification: str

    @validator('justification')
    def justification_must_be_meaningful(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError('Justificativa de cancelamento deve ter no mínimo 10 caracteres')
        return v.strip()


@router.post("/pos/{po_id}/cancel")
async def cancel_purchase_order(
    po_id: str,
    body: CancelPORequest,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    FF-HARDENING-012.1 [Item 1 & 2] — Cancel a Purchase Order with mandatory justification.

    Sets status_macro = "CANCELLED", persists the cancellation justification to
    sla_justification_text (along with who cancelled and when), and writes an
    immutable AuditLog entry so the action is fully traceable.

    A cancelled PO will never appear on the Kanban board (board query excludes
    statuses not in the active column list, and CANCELLED maps to 'Cancelado'
    which is not rendered as a column).

    Accessible to: all authenticated users (operator, leader, master, admin).
    """
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()

    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {po_id} não encontrado"
        )

    if po.status_macro == "CANCELLED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este pedido já está cancelado."
        )

    if po.status_macro in ("ARCHIVED", "ARCHIVED_PARTITIONED", "COMPLETED"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível cancelar um pedido com status '{po.status_macro}'."
        )

    from_status = po.status_macro

    # Persist cancellation
    po.status_macro = "CANCELLED"
    po.sla_justification_text = body.justification
    po.sla_justification_user = current_user.name or current_user.email
    po.sla_justification_at = datetime.utcnow()
    po.sla_justification_category = "CANCELAMENTO"
    po.updated_at = datetime.utcnow()

    # Write to partition_metadata for extra auditability
    from sqlalchemy.orm.attributes import flag_modified as _flag_modified
    meta = dict(po.partition_metadata or {})
    meta["cancelled_by"] = current_user.name or current_user.email
    meta["cancelled_at"] = po.sla_justification_at.isoformat()
    meta["cancellation_justification"] = body.justification
    po.partition_metadata = meta
    _flag_modified(po, "partition_metadata")

    # Audit log
    log_po_status_transition(
        db=db,
        po=po,
        from_status=from_status,
        to_status="CANCELLED",
        current_user=current_user,
        justification=body.justification,
        is_exception=False,
        extra_data={
            "action_type": "CANCEL_PO",
            "cancelled_by": current_user.name or current_user.email,
        }
    )

    # FF-HARDENING-012.4 Item 2: Cascade cancellation to child POs.
    # When the parent is in WAITING_COMMERCIAL_PARTITION, the child POs (C1/C2) are
    # in SUBMITTED status and appear in the Comercial column.  Cancelling only the
    # parent leaves those cards orphaned on the board.  We cascade CANCELLED to each
    # child so they physically leave the Comercial column immediately.
    if from_status == "WAITING_COMMERCIAL_PARTITION":
        child_pos = db.query(PurchaseOrder).filter(
            PurchaseOrder.parent_po_id == po.id,
            PurchaseOrder.tenant_id == current_user.tenant_id
        ).all()
        cancelled_at_str = po.sla_justification_at.isoformat()
        for child in child_pos:
            if child.status_macro not in ("CANCELLED", "ARCHIVED", "ARCHIVED_PARTITIONED", "COMPLETED"):
                child_from_status = child.status_macro
                child.status_macro = "CANCELLED"
                child.sla_justification_text = body.justification
                child.sla_justification_user = current_user.name or current_user.email
                child.sla_justification_at = po.sla_justification_at
                child.sla_justification_category = "CANCELAMENTO"
                child.updated_at = datetime.utcnow()
                child_meta = dict(child.partition_metadata or {})
                child_meta["cancelled_by"] = current_user.name or current_user.email
                child_meta["cancelled_at"] = cancelled_at_str
                child_meta["cancellation_justification"] = body.justification
                child_meta["cancelled_with_parent"] = str(po.id)
                child.partition_metadata = child_meta
                _flag_modified(child, "partition_metadata")
                log_po_status_transition(
                    db=db,
                    po=child,
                    from_status=child_from_status,
                    to_status="CANCELLED",
                    current_user=current_user,
                    justification=f"Cancelamento em cascata do pedido pai {po.po_number}: {body.justification}",
                    is_exception=False,
                    extra_data={
                        "action_type": "CANCEL_PO_CASCADE",
                        "parent_po_id": str(po.id),
                        "parent_po_number": po.po_number,
                        "cancelled_by": current_user.name or current_user.email,
                    }
                )

    db.commit()
    db.refresh(po)

    return {
        "success": True,
        "message": f"Pedido {po.po_number} cancelado com sucesso.",
        "po_id": po_id,
        "po_number": po.po_number,
        "from_status": from_status,
        "to_status": "CANCELLED",
        "justification": body.justification,
        "cancelled_by": current_user.name or current_user.email,
        "cancelled_at": po.sla_justification_at.isoformat()
    }


@router.post("/move-status", response_model=MoveStatusResponse)
async def move_po_status(
    request: MoveStatusRequest,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Move a Purchase Order to a new status using the Workflow Service.
    
    This endpoint validates the state transition and updates the PO status
    if all validation rules pass.
    
    **Salto de Etapa (LEADER/MASTER):**
    - Usuários com role LEADER ou MASTER podem pular etapas
    - Requer skip_validation=True e justificativa_lider (mínimo 10 caracteres)
    - Registra no AuditLog com is_exception=True
    
    **Parameters:**
    - **po_id**: Purchase Order ID
    - **to_status**: Target status
    - **reason**: Optional reason for the transition
    - **metadata**: Optional additional data
    - **skip_validation**: Permitir salto de etapa (LEADER/MASTER only)
    - **justificativa_lider**: Justificativa obrigatória para salto
    
    **Returns:**
    - Result of the status transition
    """
    
    # Query database
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == request.po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {request.po_id} não encontrado"
        )
    
    from_status = po.status_macro
    
    # Convert display name to DB status if needed
    to_status_db = DISPLAY_TO_DB_STATUS.get(request.to_status, request.to_status)
    
    # Define valid transitions (bidirectional support)
    valid_transitions = {
        "DRAFT": ["SUBMITTED"],
        "SUBMITTED": ["APPROVED", "DRAFT", "WAITING_COMMERCIAL_PARTITION"],
        "APPROVED": ["WAITING_DISPATCH", "SUBMITTED", "MANUFACTURING"],
        "MANUFACTURING": ["BILLING", "APPROVED"],          # FF-HARDENING-012.2
        "BILLING": ["SHIPPING", "MANUFACTURING"],           # FF-HARDENING-012.2
        "SHIPPING": ["ARCHIVED", "BILLING"],                # FF-HARDENING-012.2
        "WAITING_DISPATCH": ["COMPLETED", "APPROVED"],
        "COMPLETED": ["WAITING_DISPATCH"],  # Allow return for corrections
        "CANCELLED": [],
        "WAITING_COMMERCIAL_PARTITION": ["SUBMITTED", "BILLING", "SHIPPING"]
    }
    
    is_exception = False
    
    # Check if transition is valid
    if to_status_db not in valid_transitions.get(from_status, []):
        # Check if user can skip validation
        if request.skip_validation:
            # Verify user has LEADER, MASTER or ADMIN role
            if current_user.role.lower() not in ["leader", "master", "admin"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Apenas usuários LEADER, MASTER ou ADMIN podem realizar salto de etapa"
                )
            
            # Justification is validated by Pydantic validator
            is_exception = True
        else:
            return MoveStatusResponse(
                success=False,
                message=f"Transição inválida de {STATUS_DISPLAY_MAP.get(from_status, from_status)} para {request.to_status}",
                po_id=request.po_id,
                from_status=STATUS_DISPLAY_MAP.get(from_status, from_status),
                to_status=request.to_status,
                validation_errors=[
                    f"Não é possível transitar de {STATUS_DISPLAY_MAP.get(from_status, from_status)} para {request.to_status}",
                    f"Transições válidas: {', '.join([STATUS_DISPLAY_MAP.get(s, s) for s in valid_transitions.get(from_status, [])])}"
                ],
                is_exception=False
            )
            
    # Special transition: if parent PO is WAITING_COMMERCIAL_PARTITION and moving to SHIPPING
    if from_status == "WAITING_COMMERCIAL_PARTITION" and to_status_db == "SHIPPING":
        # Archive parent PO and move children to SHIPPING
        children = db.query(PurchaseOrder).filter(
            PurchaseOrder.parent_po_id == po.id,
            PurchaseOrder.tenant_id == current_user.tenant_id
        ).order_by(PurchaseOrder.created_at).all()
        
        if len(children) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Este pedido não possui filhos criados para aprovar a partição"
            )
            
        parent_freight = float(po.shipping_cost or 0)
        if parent_freight == 0 and po.items:
            first_item = po.items[0]
            if first_item.extra_metadata:
                meta_freight = first_item.extra_metadata.get("freight") or first_item.extra_metadata.get("Freight")
                if meta_freight:
                    try:
                        parent_freight = float(meta_freight)
                    except ValueError:
                        pass
            if parent_freight > 0:
                po.shipping_cost = parent_freight
                
        # Split freight 50/50 initially
        children[0].shipping_cost = round(parent_freight / 2.0, 4)
        children[1].shipping_cost = round(parent_freight - (parent_freight / 2.0), 4)
        
        # Move parent PO to ARCHIVED_PARTITIONED
        po.status_macro = "ARCHIVED_PARTITIONED"
        po.updated_at = datetime.utcnow()
        
        # Move children to SHIPPING
        from sqlalchemy.orm.attributes import flag_modified
        for child in children:
            child.status_macro = "SHIPPING"
            child.partition_reason = None
            child.updated_at = datetime.utcnow()
            meta = dict(child.partition_metadata or {})
            meta["original_parent_freight"] = parent_freight
            meta["current_phase"] = "FASE_A"
            # Delete keys to kill the Awaiting Decision stamp
            if "suggested_delivery_date" in meta:
                del meta["suggested_delivery_date"]
            if "partition_reason" in meta:
                del meta["partition_reason"]
            child.partition_metadata = meta
            flag_modified(child, "partition_metadata")
            
        # Log parent transition
        log_po_status_transition(
            db=db,
            po=po,
            from_status=from_status,
            to_status="ARCHIVED_PARTITIONED",
            current_user=current_user,
            justification="Partição aprovada pelo comercial. Pedido pai arquivado. Lotes filhos enviados para Expedição.",
            extra_data={"action_type": "APPROVE_PARTITION_PARENT"}
        )
        
        # Log children transitions
        for child in children:
            log_po_status_transition(
                db=db,
                po=child,
                from_status="WAITING_COMMERCIAL_PARTITION",
                to_status="SHIPPING",
                current_user=current_user,
                justification=f"Partição criada a partir de {po.po_number}. Movido para Expedição.",
                extra_data={"action_type": "APPROVE_PARTITION_CHILD", "parent_po_number": po.po_number}
            )
            
        db.commit()
        return MoveStatusResponse(
            success=True,
            message=f"Partição do pedido {po.po_number} aprovada. Filhos enviados para Expedição.",
            po_id=str(po.id),
            from_status="Comercial",
            to_status="Faturamento/Expedição",
            validation_errors=None,
            is_exception=False
        )
    
    # Update status
    po.status_macro = to_status_db
    po.updated_at = datetime.utcnow()
    
    # Always log status transition
    log_po_status_transition(
        db=db,
        po=po,
        from_status=from_status,
        to_status=to_status_db,
        current_user=current_user,
        justification=request.justificativa_lider if is_exception else None,
        is_exception=is_exception,
        extra_data={
            "reason": request.reason,
            "metadata": request.metadata
        }
    )
    
    db.commit()
    
    message = f"Pedido {po.po_number} movido de {STATUS_DISPLAY_MAP.get(from_status, from_status)} para {request.to_status}"
    if is_exception:
        message += " (SALTO DE ETAPA EXCEPCIONAL)"
    
    return MoveStatusResponse(
        success=True,
        message=message,
        po_id=request.po_id,
        from_status=STATUS_DISPLAY_MAP.get(from_status, from_status),
        to_status=request.to_status,
        validation_errors=None,
        is_exception=is_exception
    )


@router.get("/items")
async def list_items(
    status: Optional[str] = Query(None, description="Filter by item status"),
    sku: Optional[str] = Query(None, description="Filter by SKU"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all items across all POs with optional filters.
    
    **Query Parameters:**
    - **status**: Filter by item status
    - **sku**: Filter by SKU (partial match)
    - **skip**: Pagination offset
    - **limit**: Maximum number of results
    
    **Returns:**
    - List of items with their PO information
    """
    
    # Query database
    query = db.query(OrderItem).filter(
        OrderItem.tenant_id == current_user.tenant_id
    )
    
    # Apply filters
    if status:
        query = query.filter(OrderItem.status_item == status)
    
    if sku:
        query = query.filter(OrderItem.sku.ilike(f"%{sku}%"))
    
    # Apply pagination
    items = query.offset(skip).limit(limit).all()
    
    # Convert to response
    result_items = []
    for item in items:
        po = item.purchase_order
        result_items.append({
            "id": str(item.id),
            "sku": item.sku,
            "quantity": item.quantity,
            "price": float(item.price),
            "status_item": item.status_item,
            "po_id": str(po.id),
            "po_number": po.po_number,
            "client_name": "Cliente",
            "po_status": STATUS_DISPLAY_MAP.get(po.status_macro, po.status_macro),
            "created_at": item.created_at.isoformat(),
            "updated_at": item.updated_at.isoformat()
        })
    
    total = db.query(OrderItem).filter(
        OrderItem.tenant_id == current_user.tenant_id
    ).count()
    
    return {
        "items": result_items,
        "total": total,
        "skip": skip,
        "limit": limit
    }


@router.put("/pos/{po_id}/commission", response_model=UpdateCommissionResponse)
async def update_manual_commission(
    po_id: str,
    request: UpdateCommissionRequest,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update manual commission rate for a PO (MASTER/ADMIN only).
    
    This endpoint allows MASTER or ADMIN users to override the automatic
    commission calculation with a manual rate.
    
    **Authorization:**
    - Only users with MASTER or ADMIN role can update commission
    
    **Parameters:**
    - **po_id**: Purchase Order ID
    - **manual_commission_rate**: New commission rate (0-100%)
    - **justification**: Reason for manual override (min 10 characters)
    
    **Returns:**
    - Updated commission details and recalculated margin
    """
    
    # Check authorization
    if current_user.role.lower() not in ["master", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas usuários MASTER ou ADMIN podem alterar a comissão manualmente"
        )
    
    # Query PO
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {po_id} não encontrado"
        )
        
    if po.status_macro == "ARCHIVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é permitido alterar a comissão de um pedido arquivado."
        )
    
    # Update commission rate in PO metadata
    meta = dict(po.partition_metadata) if po.partition_metadata else {}
    meta["manual_commission_rate"] = float(request.manual_commission_rate)
    meta["commission_justification"] = request.justification
    meta["commission_updated_by"] = str(current_user.id)
    meta["commission_updated_at"] = datetime.utcnow().isoformat()
    po.partition_metadata = meta
    
    # If updating specific item
    if request.item_id:
        item = db.query(OrderItem).filter(
            OrderItem.id == request.item_id,
            OrderItem.po_id == po_id,
            OrderItem.tenant_id == current_user.tenant_id
        ).first()
        
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Item {request.item_id} não encontrado"
            )
        
        # Update item's manual commission rate with explicit dictionary reassignment for mutability tracking
        item_meta = dict(item.extra_metadata) if item.extra_metadata else {}
        item_meta["manual_commission_rate"] = float(request.manual_commission_rate)
        item_meta["commission_justification"] = request.justification
        item_meta["commission_updated_by"] = str(current_user.id)
        item_meta["commission_updated_at"] = datetime.utcnow().isoformat()
        item.extra_metadata = item_meta
        flag_modified(item, "extra_metadata")
    
    po.updated_at = datetime.utcnow()
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(po, "partition_metadata")
    db.commit()
    db.refresh(po)
    
    # Recalculate metrics with new commission
    from backend.services.financial_service import FinancialService
    
    metrics = calculate_po_metrics(po)
    
    # Calculate commission with manual override
    commission_value = FinancialService.calculate_commission_value(
        metrics["total_value"],
        request.manual_commission_rate
    )
    
    return UpdateCommissionResponse(
        success=True,
        message=f"Comissão atualizada para {request.manual_commission_rate}% com sucesso",
        po_id=po_id,
        new_commission_rate=request.manual_commission_rate,
        new_margin=metrics["margin_percentage"],
        updated_by=current_user.username
    )


@router.put("/pos/{po_id}/logistics-checklist", response_model=UpdateLogisticsChecklistResponse)
async def update_logistics_checklist(
    po_id: str,
    request: UpdateLogisticsChecklistRequest,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update logistics checklist for a PO in Expedição/Faturamento stage.
    
    This endpoint manages the logistics checklist with 3 mandatory items:
    - Endereço Conferido
    - Peso Validado
    - Etiquetas Impressas
    
    And 2 evidence uploads:
    - Foto da Carga
    - Foto do Canhoto/NF
    
    **Parameters:**
    - **po_id**: Purchase Order ID
    - **endereco_conferido**: Address verified checkbox
    - **peso_validado**: Weight validated checkbox
    - **etiquetas_impressas**: Labels printed checkbox
    - **foto_carga_path**: Path to cargo photo
    - **foto_canhoto_path**: Path to delivery receipt/invoice photo
    
    **Returns:**
    - Updated checklist status and dispatch readiness
    """
    
    # Query PO
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {po_id} não encontrado"
        )
        
    if po.status_macro == "ARCHIVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é permitido alterar o checklist logístico de um pedido arquivado."
        )
    
    logistics_checklist = {
        "endereco_conferido": request.endereco_conferido,
        "peso_validado": request.peso_validado,
        "etiquetas_impressas": request.etiquetas_impressas,
        "foto_carga_path": request.foto_carga_path,
        "foto_canhoto_path": request.foto_canhoto_path,
        "updated_by": str(current_user.id),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    # Reassign the metadata dictionary to trigger SQLAlchemy's observer
    meta = dict(po.partition_metadata or {})
    meta["logistics_checklist"] = logistics_checklist
    # Flatten root keys
    if request.foto_carga_path:
        meta["foto_carga_path"] = request.foto_carga_path
    if request.foto_canhoto_path:
        meta["foto_canhoto_path"] = request.foto_canhoto_path
    po.partition_metadata = meta
    po.updated_at = datetime.utcnow()
    
    # Check if all requirements are met
    checklist_complete = (
        request.endereco_conferido and
        request.peso_validado and
        request.etiquetas_impressas
    )
    
    evidence_complete = (
        request.foto_carga_path is not None and
        request.foto_canhoto_path is not None
    )
    
    can_dispatch = checklist_complete and evidence_complete
    
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(po, "partition_metadata")
    db.commit()
    db.refresh(po)
    
    is_privileged = current_user.role.lower() in ["admin", "master"]
    mapped_po = _map_single_po(po, db, is_privileged)
    
    message = "Checklist de logística atualizado com sucesso"
    if can_dispatch:
        message += " - Pronto para despacho!"
    elif not checklist_complete:
        message += " - Pendente: completar todos os itens do checklist"
    elif not evidence_complete:
        message += " - Pendente: enviar todas as evidências fotográficas"
    
    return UpdateLogisticsChecklistResponse(
        success=True,
        message=message,
        po_id=po_id,
        checklist_complete=checklist_complete,
        can_dispatch=can_dispatch,
        po=mapped_po
    )


@router.get("/pos/{po_id}/logistics-checklist")
async def get_logistics_checklist(
    po_id: str,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get logistics checklist status for a PO.
    
    **Parameters:**
    - **po_id**: Purchase Order ID
    
    **Returns:**
    - Current checklist status and evidence paths
    """
    
    # Query PO
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {po_id} não encontrado"
        )
    
    # Get logistics checklist from metadata
    logistics_checklist = {}
    if po.partition_metadata and "logistics_checklist" in po.partition_metadata:
        logistics_checklist = dict(po.partition_metadata["logistics_checklist"])
    else:
        # Return default empty checklist
        logistics_checklist = {
            "endereco_conferido": False,
            "peso_validado": False,
            "etiquetas_impressas": False,
            "foto_carga_path": None,
            "foto_canhoto_path": None
        }
    
    # Fall back to root partition_metadata keys if present
    if po.partition_metadata:
        if "foto_carga_path" in po.partition_metadata:
            logistics_checklist["foto_carga_path"] = po.partition_metadata["foto_carga_path"]
        if "foto_canhoto_path" in po.partition_metadata:
            logistics_checklist["foto_canhoto_path"] = po.partition_metadata["foto_canhoto_path"]
    
    # Check completion status
    checklist_complete = (
        logistics_checklist.get("endereco_conferido", False) and
        logistics_checklist.get("peso_validado", False) and
        logistics_checklist.get("etiquetas_impressas", False)
    )
    
    evidence_complete = (
        logistics_checklist.get("foto_carga_path") is not None and
        logistics_checklist.get("foto_canhoto_path") is not None
    )
    
    can_dispatch = checklist_complete and evidence_complete
    
    return {
        "po_id": po_id,
        "checklist": logistics_checklist,
        "checklist_complete": checklist_complete,
        "evidence_complete": evidence_complete,
        "can_dispatch": can_dispatch
    }


@router.post("/advance-status")
async def advance_po_status(
    po_id: str,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Advance PO to the next status in the workflow.
    Validates mandatory fields before advancing.
    """
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {po_id} não encontrado"
        )
    
    current_status = po.status_macro
    # Expedition Dual-Phase Switch (The 'Fabio Monteiro' Rule):
    # Phase A (🚛 AJUSTE DE FRETE): If the PO came from a partition request, transition back to PCP (APPROVED) on advance
    # ONLY if freight has not been allocated yet AND the current status is BILLING (Faturamento)
    meta = po.partition_metadata or {}
    if current_status == "BILLING" and po.parent_po_id is not None and not meta.get("freight_allocated"):
        next_status = "APPROVED"
    else:
        next_status = STATUS_FLOW.get(current_status, {}).get("next")
    
    if not next_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não há próxima etapa após {STATUS_DISPLAY_MAP.get(current_status, current_status)}"
        )
    
    # Validate mandatory fields based on current status
    validation_errors = []
    
    if current_status == "DRAFT":
        # Comercial must have client_name and items
        if not getattr(po, 'client_name', None):
            validation_errors.append("Nome do cliente é obrigatório")
        if not po.items or len(po.items) == 0:
            validation_errors.append("Pedido deve ter pelo menos um item")
    
    elif current_status == "SUBMITTED":
        # PCP must validate items
        if not po.items or len(po.items) == 0:
            validation_errors.append("Pedido deve ter itens validados")
    
    elif current_status == "APPROVED":
        # Production must have items processed
        pass  # Add production-specific validations if needed
    
    elif current_status == "BILLING":
        # FF-HARDENING-012.2: Faturamento must have NF-e number, Transportadora, and emission date
        meta = po.partition_metadata or {}
        # Only validate for standard (non-FASE_A partition) flow
        if po.parent_po_id is None or meta.get("freight_allocated"):
            nfe = meta.get("numero_nfe") or (po.partition_metadata or {}).get("numero_nfe") or ""
            carrier = meta.get("transportadora") or (po.partition_metadata or {}).get("transportadora") or ""
            emission = meta.get("data_emissao_nf") or (po.partition_metadata or {}).get("data_emissao_nf") or ""
            if not nfe:
                validation_errors.append("Número NF-e é obrigatório")
            if not carrier:
                validation_errors.append("Transportadora é obrigatória")
            if not emission:
                validation_errors.append("Data de emissão da NF-e é obrigatória")

    elif current_status == "SHIPPING":
        # Expedição: validate checklist only for standard Phase B
        meta = po.partition_metadata or {}
        if po.parent_po_id is None or meta.get("freight_allocated"):
            # Expedition must have logistical checklist complete
            nfe = meta.get("numero_nfe") or ""
            carrier = meta.get("transportadora") or ""
            if not nfe:
                validation_errors.append("Número NF-e é obrigatório")
            if not carrier:
                validation_errors.append("Transportadora é obrigatória")
            if "logistics_checklist" in meta:
                checklist = meta["logistics_checklist"]
                if not all([
                    checklist.get("endereco_conferido"),
                    checklist.get("peso_validado"),
                    checklist.get("etiquetas_impressas")
                ]):
                    validation_errors.append("Checklist de logística deve estar completo (Endereço, Peso e Etiquetas)")
            else:
                validation_errors.append("Checklist de logística não encontrado")
            
    elif current_status == "WAITING_DISPATCH":
        # Dispatch must have logistics checklist complete
        if po.partition_metadata and "logistics_checklist" in po.partition_metadata:
            checklist = po.partition_metadata["logistics_checklist"]
            if not all([
                checklist.get("endereco_conferido"),
                checklist.get("peso_validado"),
                checklist.get("etiquetas_impressas")
            ]):
                validation_errors.append("Checklist de logística deve estar completo (Endereço, Peso e Etiquetas)")
        else:
            validation_errors.append("Checklist de logística não encontrado")
    
    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Validação falhou", "errors": validation_errors}
        )
    
    # Update status
    po.status_macro = next_status
    po.updated_at = datetime.utcnow()
    
    # Clean up return priority note upon successful advance
    if po.partition_metadata and "priority_note" in po.partition_metadata:
        meta = dict(po.partition_metadata)
        meta.pop("priority_note", None)
        po.partition_metadata = meta
    
    # Log status transition
    # UAT-FIX-4 (extended): Log "CONFERIDO (TROCA/DEVOLUÇÃO)" for ALL forward advances of
    # exchange/return cards, not just the first Comercial→PCP hop.
    # Detection order:
    #   1. Any OrderItem has is_exchange_return flag in extra_metadata
    #   2. partition_metadata has is_exchange_return flag (set by ExchangeCard endpoint)
    #   3. po_number starts with "TR-" (naming convention for manual exchange cards)
    is_exchange = (
        any(item.extra_metadata and item.extra_metadata.get("is_exchange_return") for item in po.items)
        if po.items else False
    )
    if not is_exchange:
        is_exchange = bool(po.partition_metadata and po.partition_metadata.get("is_exchange_return"))
    if not is_exchange:
        is_exchange = (po.po_number or "").startswith("TR-")

    if next_status == "ARCHIVED":
        justification = "FINALIZADO"
    elif is_exchange:
        # All forward transitions of exchange/return cards use this label
        justification = "CONFERIDO (TROCA/DEVOLU\u00c7\u00c3O)"
    else:
        justification = None
    log_po_status_transition(
        db=db,
        po=po,
        from_status=current_status,
        to_status=next_status,
        current_user=current_user,
        justification=justification,
        is_exception=False
    )
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Pedido avançado para {STATUS_DISPLAY_MAP.get(next_status, next_status)}",
        "po_id": po_id,
        "from_status": STATUS_DISPLAY_MAP.get(current_status, current_status),
        "to_status": STATUS_DISPLAY_MAP.get(next_status, next_status)
    }


@router.post("/return-status")
async def return_po_status(
    po_id: str,
    reason: str,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Return PO to the previous status in the workflow.
    Requires a mandatory reason (min 10 chars) and logs in AuditLog.
    Enforces the mandatory return labels dropdown.
    """
    if not reason or len(reason.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Motivo da devolução deve ter pelo menos 10 caracteres"
        )
    
    # Enforce dropdown return labels
    valid_labels = ["[Particionamento]", "[Ajuste de Personalização]", "[Erro de Dados ONET]", "[Outros]"]
    reason_clean = reason.strip()
    if not any(reason_clean.startswith(label) for label in valid_labels):
        reason_clean = f"[Outros]: {reason_clean}"
        
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {po_id} não encontrado"
        )
    
    current_status = po.status_macro
    prev_status = STATUS_FLOW.get(current_status, {}).get("prev")
    
    if not prev_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Não é possível devolver de {STATUS_DISPLAY_MAP.get(current_status, current_status)}"
        )
    
    # Update status
    from_status = current_status
    po.status_macro = prev_status
    po.updated_at = datetime.utcnow()
    
    # Save justification to po.partition_metadata["priority_note"]
    if po.partition_metadata is None:
        po.partition_metadata = {}
    meta = dict(po.partition_metadata)
    meta["priority_note"] = {
        "text": reason_clean,
        "from_area": STATUS_DISPLAY_MAP.get(from_status, from_status),
        "target_area": STATUS_DISPLAY_MAP.get(prev_status, prev_status),
        "timestamp": datetime.utcnow().isoformat(),
        "user": current_user.name or current_user.email or "Sistema"
    }
    po.partition_metadata = meta
    
    # Create audit log for return
    log_po_status_transition(
        db=db,
        po=po,
        from_status=from_status,
        to_status=prev_status,
        current_user=current_user,
        justification=f"DEVOLUÇÃO: {reason_clean}",
        is_exception=False,
        extra_data={
            "return_reason": reason_clean,
            "action_type": "RETURN"
        }
    )
    
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(po, "partition_metadata")
    db.commit()
    db.refresh(po)
    
    return {
        "success": True,
        "message": f"Pedido devolvido para {STATUS_DISPLAY_MAP.get(prev_status, prev_status)}",
        "po_id": po_id,
        "from_status": STATUS_DISPLAY_MAP.get(from_status, from_status),
        "to_status": STATUS_DISPLAY_MAP.get(prev_status, prev_status),
        "reason": reason_clean
    }


from typing import Dict

class CreditApprovalBody(BaseModel):
    audit_comment: str

class CommercialRejectBody(BaseModel):
    justification: str

@router.post("/pos/{po_id}/approve-credit")
async def approve_credit(
    po_id: str,
    body: CreditApprovalBody,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {po_id} não encontrado"
        )
        
    from_status = po.status_macro
    po.status_macro = "APPROVED"
    po.updated_at = datetime.utcnow()
    
    if po.partition_metadata is None:
        po.partition_metadata = {}
    meta = dict(po.partition_metadata)
    meta["audit_comment"] = body.audit_comment
    meta["block_status"] = "LIBERADO"
    meta["credit_reproved"] = False
    po.partition_metadata = meta
    
    for item in po.items:
        if item.extra_metadata:
            item_meta = dict(item.extra_metadata)
            item_meta["block_status"] = "LIBERADO"
            item.extra_metadata = item_meta
        item.status_item = "APPROVED"
        
    log_po_status_transition(
        db=db,
        po=po,
        from_status=from_status,
        to_status="APPROVED",
        current_user=current_user,
        justification=f"CRÉDITO APROVADO: {body.audit_comment}",
        is_exception=False
    )
    
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(po, "partition_metadata")
    db.commit()
    db.refresh(po)
    return {"success": True, "message": "Crédito aprovado com sucesso. Pedido enviado para o PCP."}

@router.post("/pos/{po_id}/maintain-block")
async def maintain_block(
    po_id: str,
    body: CreditApprovalBody,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {po_id} não encontrado"
        )
        
    from_status = po.status_macro
    po.status_macro = "SUBMITTED"
    po.updated_at = datetime.utcnow()
    
    if po.partition_metadata is None:
        po.partition_metadata = {}
    meta = dict(po.partition_metadata)
    meta["audit_comment"] = body.audit_comment
    meta["block_status"] = "BLOQUEADO"
    meta["credit_reproved"] = True
    po.partition_metadata = meta
    
    for item in po.items:
        if item.extra_metadata:
            item_meta = dict(item.extra_metadata)
            item_meta["block_status"] = "BLOQUEADO"
            item.extra_metadata = item_meta
        item.status_item = "ANALISE_CREDITO"
        
    log_po_status_transition(
        db=db,
        po=po,
        from_status=from_status,
        to_status="SUBMITTED",
        current_user=current_user,
        justification=f"MANTER BLOQUEIO: {body.audit_comment}",
        is_exception=False
    )
    
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(po, "partition_metadata")
    db.commit()
    db.refresh(po)
    return {"success": True, "message": "Bloqueio mantido. Pedido devolvido para o Comercial."}

@router.post("/pos/{po_id}/commercial-reject")
async def commercial_reject(
    po_id: str,
    body: CommercialRejectBody,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not body.justification or len(body.justification.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Justificativa de rejeição deve ter pelo menos 10 caracteres"
        )
        
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {po_id} não encontrado"
        )
        
    from_status = po.status_macro
    po.status_macro = "CANCELLED"
    po.updated_at = datetime.utcnow()

    if po.partition_metadata is None:
        po.partition_metadata = {}
    meta = dict(po.partition_metadata)
    meta["rejection_flag"] = "REJEITADO COMERCIAL"
    meta["commercial_rejection_reason"] = body.justification
    meta["cancelled_by"] = current_user.name or current_user.email
    meta["cancelled_at"] = datetime.utcnow().isoformat()
    po.partition_metadata = meta

    # FF-HARDENING-013 Issue A: Log with the canonical CONFERIDO action text
    log_po_status_transition(
        db=db,
        po=po,
        from_status=from_status,
        to_status="CANCELLED",
        current_user=current_user,
        justification="CONFERIDO - NÃO APROVADO PARTIÇÃO (CANCELADO)",
        extra_data={
            "action_type": "COMMERCIAL_REJECT",
            "rejection_flag": "REJEITADO COMERCIAL",
            "rejection_reason": body.justification
        }
    )

    # FF-HARDENING-013 Issue A: Cascade CANCELLED to child POs (e.g. C1/C2 in SUBMITTED)
    child_pos = db.query(PurchaseOrder).filter(
        PurchaseOrder.parent_po_id == po.id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).all()
    cancelled_at_str = datetime.utcnow().isoformat()
    for child in child_pos:
        if child.status_macro not in ("CANCELLED", "ARCHIVED", "ARCHIVED_PARTITIONED", "COMPLETED"):
            child_from_status = child.status_macro
            child.status_macro = "CANCELLED"
            child.updated_at = datetime.utcnow()
            child_meta = dict(child.partition_metadata or {})
            child_meta["rejection_flag"] = "REJEITADO COMERCIAL"
            child_meta["commercial_rejection_reason"] = body.justification
            child_meta["cancelled_with_parent"] = str(po.id)
            child_meta["cancelled_at"] = cancelled_at_str
            child.partition_metadata = child_meta
            from sqlalchemy.orm.attributes import flag_modified as _flag_child
            _flag_child(child, "partition_metadata")
            log_po_status_transition(
                db=db,
                po=child,
                from_status=child_from_status,
                to_status="CANCELLED",
                current_user=current_user,
                justification="CONFERIDO - NÃO APROVADO PARTIÇÃO (CANCELADO)",
                extra_data={
                    "action_type": "COMMERCIAL_REJECT_CASCADE",
                    "parent_po_id": str(po.id),
                    "parent_po_number": po.po_number,
                }
            )

    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(po, "partition_metadata")
    db.commit()
    db.refresh(po)

    return {
        "success": True,
        "message": "Partição rejeitada e cancelada pelo Comercial com sucesso",
        "po_id": po_id,
        "status": po.status_macro
    }

class SuggestPartitionBody(BaseModel):
    po_id: Optional[str] = None
    reason: Optional[str] = None
    qty_splits: Optional[Dict[str, List[float]]] = None  # FF-HARDENING-012.4 Item 3: float to accept decimal quantities
    new_delivery_date: Optional[str] = None

@router.post("/suggest-partition")
async def suggest_partition(
    payload: Optional[SuggestPartitionBody] = None,
    po_id: Optional[str] = None,
    reason: Optional[str] = None,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    PCP-specific action: Suggest partition, create child POs, move parent PO status to
    WAITING_COMMERCIAL_PARTITION. Child POs are created with status_macro=SUBMITTED so
    they appear in the 'Comercial' column immediately for the commercial team to review
    and approve the partition (business rule §9.3).

    TRANSACTION SAFETY: The entire operation is wrapped in a try/except block. Any
    unexpected error after the parent PO has been updated triggers a db.rollback() to
    prevent corrupted or partial state in the database.
    """
    # Resolve parameters
    resolved_po_id = (payload.po_id if payload else None) or po_id
    resolved_reason = (payload.reason if payload else None) or reason
    qty_splits = payload.qty_splits if payload else None
    new_delivery_date_val = payload.new_delivery_date if payload else None

    if not resolved_reason or len(resolved_reason.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Motivo da sugestão de partição deve ter pelo menos 10 caracteres"
        )

    if not new_delivery_date_val:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nova data de entrega prevista é obrigatória"
        )

    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == resolved_po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()

    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {resolved_po_id} não encontrado"
        )

    if po.status_macro != "APPROVED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sugestão de partição só pode ser feita no estágio PCP"
        )

    total_quantity = sum(item.quantity for item in po.items)
    if total_quantity <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não é possível sugerir partição para um pedido com quantidade total menor ou igual a 1"
        )

    # ── STRICT TRANSACTION BLOCK ────────────────────────────────────────────────
    # All DB mutations below are wrapped so that any failure rolls back everything,
    # preventing ghost/vanished cards caused by partial writes. [Fix §1, §3]
    try:
        from sqlalchemy.orm.attributes import flag_modified

        # Update parent status to WAITING_COMMERCIAL_PARTITION
        from_status = po.status_macro
        po.status_macro = "WAITING_COMMERCIAL_PARTITION"
        po.partition_reason = resolved_reason
        po.updated_at = datetime.utcnow()

        # Store suggested_delivery_date and partition_reason in the parent's partition_metadata
        if po.partition_metadata is None:
            po.partition_metadata = {}
        meta = dict(po.partition_metadata)
        meta["suggested_delivery_date"] = new_delivery_date_val
        meta["partition_reason"] = resolved_reason
        po.partition_metadata = meta
        flag_modified(po, "partition_metadata")

        # Commit parent PO status change
        db.commit()
        db.refresh(po)

        # Extract expected delivery date of the parent PO
        parent_delivery_date = po.expected_delivery_date
        parent_delivery_date_str = parent_delivery_date.isoformat() if parent_delivery_date else None

        # Extract inherited flags from parent metadata with dynamic fallback to items
        parent_metadata = po.partition_metadata or {}

        parent_is_personalized = parent_metadata.get("is_personalized")
        if parent_is_personalized is None:
            parent_is_personalized = any(
                getattr(item, "is_personalized", False)
                or (item.extra_metadata and item.extra_metadata.get("is_personalized"))
                for item in po.items
            )

        parent_is_export = parent_metadata.get("is_export")
        if parent_is_export is None:
            parent_is_export = any(
                item.extra_metadata and item.extra_metadata.get("is_export")
                for item in po.items
            )

        parent_is_new_client = parent_metadata.get("is_new_client")
        if parent_is_new_client is None:
            parent_is_new_client = any(
                getattr(item, "is_new_client", False)
                or (item.extra_metadata and item.extra_metadata.get("is_new_client"))
                for item in po.items
            )

        parent_is_replacement = parent_metadata.get("is_replacement")
        if parent_is_replacement is None:
            parent_is_replacement = any(
                item.extra_metadata and item.extra_metadata.get("is_replacement")
                for item in po.items
            )

        parent_customization_notes = parent_metadata.get("customization_notes")
        if parent_customization_notes is None:
            notes_list = [
                getattr(item, "customization_notes", None)
                or (item.extra_metadata.get("customization_notes") if item.extra_metadata else None)
                for item in po.items
            ]
            parent_customization_notes = next((n for n in notes_list if n), None)

        parent_attachment_path = parent_metadata.get("attachment_path")
        if parent_attachment_path is None:
            attachments = [
                getattr(item, "attachment_path", None)
                or (item.extra_metadata.get("attachment_path") if item.extra_metadata else None)
                for item in po.items
            ]
            parent_attachment_path = next((a for a in attachments if a), None)

        parent_packaging_type = parent_metadata.get("packaging_type")
        if parent_packaging_type is None:
            packagings = [
                item.extra_metadata.get("packaging_type") if item.extra_metadata else None
                for item in po.items
            ]
            parent_packaging_type = next((p for p in packagings if p), None)

        import math
        # Precompute split quantities
        splits = []
        for idx, item in enumerate(po.items):
            q1, q2 = 0, 0
            if qty_splits and (str(item.id) in qty_splits or item.sku in qty_splits):
                split = qty_splits.get(str(item.id)) or qty_splits.get(item.sku)
                # FF-HARDENING-012.4 Item 3: use float() to accept decimal split quantities
                q1, q2 = float(split[0]), float(split[1])
                # Tolerance-based sum check to handle floating-point rounding (e.g., 5.5 + 5.0 = 10.5)
                if abs((q1 + q2) - float(item.quantity)) > 0.001:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"A soma das quantidades divididas ({q1} + {q2}) para o item "
                            f"{item.sku} deve ser igual à quantidade original ({item.quantity})"
                        )
                    )
            else:
                # Fallback auto split
                if item.quantity > 1:
                    q1 = int(math.ceil(item.quantity / 2.0))
                    q2 = item.quantity - q1
                else:
                    if idx % 2 == 0:
                        q1 = 1
                        q2 = 0
                    else:
                        q1 = 0
                        q2 = 1
            splits.append((item, q1, q2))

        # ── FIX §9.3: Child POs must be created with status_macro="SUBMITTED" ─────
        # Previously "WAITING_COMMERCIAL_PARTITION" caused both children to be
        # suppressed by the board query (line 341-343 excludes child POs in that
        # status), making the cards completely disappear from the Kanban board.
        # With SUBMITTED they land in the 'Comercial' column immediately, where the
        # commercial team will see them and can approve or reject the partition.
        CHILD_STATUS = "SUBMITTED"

        # Step 1: Create child1 object.
        child1 = PurchaseOrder(
            tenant_id=uuid.UUID(str(po.tenant_id)),
            po_number=f"{po.po_number}-C1",
            status_macro=CHILD_STATUS,  # FIX §9.3 — Comercial column
            parent_po_id=uuid.UUID(str(po.id)),
            shipping_cost=0.0000,  # 4-decimal precision internally!
            is_partitioned=False,
            partition_reason=resolved_reason,
            partition_metadata={
                "client_name": po.client_name,
                "expected_delivery_date": parent_delivery_date_str,
                "parent_po_number": po.po_number,
                "partition_type": "CHILD_1",
                "is_personalized": parent_is_personalized,
                "is_export": parent_is_export,
                "is_new_client": parent_is_new_client,
                "is_replacement": parent_is_replacement,
                "customization_notes": parent_customization_notes,
                "attachment_path": parent_attachment_path,
                "packaging_type": parent_packaging_type
            }
        )

        # Step 2: db.add(child1) -> db.commit() -> db.refresh(child1).
        db.add(child1)
        db.commit()
        db.refresh(child1)

        # Step 3: Create items for child1 using the committed child1.id.
        for item, q1, q2 in splits:
            if q1 > 0:
                c1_item_extra = dict(item.extra_metadata or {})
                if parent_delivery_date_str:
                    c1_item_extra["delivery_date"] = parent_delivery_date_str
                    c1_item_extra["expected_delivery_date"] = parent_delivery_date_str

                c1_item = OrderItem(
                    po_id=uuid.UUID(str(child1.id)),
                    tenant_id=uuid.UUID(str(po.tenant_id)),
                    sku=item.sku,
                    quantity=q1,
                    price=item.price,
                    status_item=item.status_item,
                    unit_value=item.unit_value,
                    item_total_value=float(item.price) * q1,
                    is_personalized=item.is_personalized,
                    is_new_client=item.is_new_client,
                    customization_notes=item.customization_notes,
                    attachment_path=item.attachment_path,
                    extra_metadata=c1_item_extra
                )
                db.add(c1_item)
        db.commit()

        # Step 4: Create child2 object.
        child2 = PurchaseOrder(
            tenant_id=uuid.UUID(str(po.tenant_id)),
            po_number=f"{po.po_number}-C2",
            status_macro=CHILD_STATUS,  # FIX §9.3 — Comercial column
            parent_po_id=uuid.UUID(str(po.id)),
            shipping_cost=0.0000,  # 4-decimal precision internally!
            is_partitioned=False,
            partition_reason=resolved_reason,
            partition_metadata={
                "client_name": po.client_name,
                "expected_delivery_date": new_delivery_date_val,
                "parent_po_number": po.po_number,
                "partition_type": "CHILD_2",
                "is_personalized": parent_is_personalized,
                "is_export": parent_is_export,
                "is_new_client": parent_is_new_client,
                "is_replacement": parent_is_replacement,
                "customization_notes": parent_customization_notes,
                "attachment_path": parent_attachment_path,
                "packaging_type": parent_packaging_type
            }
        )

        # Step 5: db.add(child2) -> db.commit() -> db.refresh(child2).
        db.add(child2)
        db.commit()
        db.refresh(child2)

        # Step 6: Create items for child2 using the committed child2.id.
        for item, q1, q2 in splits:
            if q2 > 0:
                c2_item_extra = dict(item.extra_metadata or {})
                c2_item_extra["delivery_date"] = new_delivery_date_val
                c2_item_extra["expected_delivery_date"] = new_delivery_date_val

                c2_item = OrderItem(
                    po_id=uuid.UUID(str(child2.id)),
                    tenant_id=uuid.UUID(str(po.tenant_id)),
                    sku=item.sku,
                    quantity=q2,
                    price=item.price,
                    status_item=item.status_item,
                    unit_value=item.unit_value,
                    item_total_value=float(item.price) * q2,
                    is_personalized=item.is_personalized,
                    is_new_client=item.is_new_client,
                    customization_notes=item.customization_notes,
                    attachment_path=item.attachment_path,
                    extra_metadata=c2_item_extra
                )
                db.add(c2_item)
        db.commit()

        # Compute total values after refresh to ensure items are loaded
        db.refresh(child1)
        db.refresh(child2)
        child1.po_total_value = sum(float(it.item_total_value or 0) for it in child1.items)
        child2.po_total_value = sum(float(it.item_total_value or 0) for it in child2.items)
        db.add(child1)
        db.add(child2)
        db.commit()

        # Create audit log
        log_po_status_transition(
            db=db,
            po=po,
            from_status=from_status,
            to_status="WAITING_COMMERCIAL_PARTITION",
            current_user=current_user,
            justification=f"SUGESTÃO DE PARTIÇÃO: {resolved_reason}",
            is_exception=False,
            extra_data={
                "partition_reason": resolved_reason,
                "action_type": "SUGGEST_PARTITION",
                "child1_id": str(child1.id),
                "child2_id": str(child2.id),
                "child1_status": CHILD_STATUS,
                "child2_status": CHILD_STATUS
            }
        )

        db.commit()

        return {
            "success": True,
            "message": "Sugestão de partição enviada para Comercial",
            "po_id": resolved_po_id,
            "from_status": STATUS_DISPLAY_MAP.get(from_status, from_status),
            "to_status": STATUS_DISPLAY_MAP.get("WAITING_COMMERCIAL_PARTITION", "Aguardando Partição"),
            "reason": resolved_reason,
            "child1_id": str(child1.id),
            "child2_id": str(child2.id)
        }

    except HTTPException:
        # Validation errors — not a DB corruption, re-raise as-is
        db.rollback()
        raise
    except Exception as exc:
        # Any unexpected error after the parent PO update — rollback everything
        # to prevent ghost rows and vanished cards. [Fix §3]
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao processar partição. Operação revertida: {str(exc)}"
        )


@router.post("/pos/{po_id}/archive")
async def archive_purchase_order(
    po_id: str,
    payload: dict,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Finalize audit, archive the PO definitively (removing from Kanban), and seal blockchain hash.
    """
    import uuid
    from datetime import datetime
    try:
        uuid.UUID(po_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {po_id} não encontrado"
        )

    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {po_id} não encontrado"
        )
        
    audit_comment = payload.get("audit_comment", "").strip()
    if len(audit_comment) < 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O comentário de auditoria deve conter pelo menos 20 caracteres."
        )
        
    # Save comment to metadata
    if po.partition_metadata is None:
        po.partition_metadata = {}
    meta = dict(po.partition_metadata)
    meta["audit_comment"] = audit_comment
    po.partition_metadata = meta
    
    from_status = po.status_macro
    to_status = "ARCHIVED"
    
    po.status_macro = to_status
    po.updated_at = datetime.utcnow()
    
    # Log status transition to seal blockchain hash
    log_po_status_transition(
        db=db,
        po=po,
        from_status=from_status,
        to_status=to_status,
        current_user=current_user,
        justification=f"AUDITORIA FINALIZADA E ARQUIVADA: {audit_comment}",
        is_exception=False,
        extra_data={
            "action_type": "ARCHIVE",
            "audit_comment": audit_comment
        }
    )
    
    db.commit()
    return {
        "success": True,
        "message": "Pedido de compra finalizado, auditado e arquivado com sucesso!",
        "po_id": po_id,
        "status": to_status
    }


@router.post("/admin/nuke-tenant-data")
def nuke_tenant_data(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Emergency clean slate: Deletes all AuditLog, OrderItem, and PurchaseOrder records
    associated with the logged-in user's tenant.

    RBAC: Requires 'admin' or 'master' role (case-insensitive).
    Runs as a synchronous def so blocking ORM DELETE queries run in the
    thread pool and do not block the event loop.
    """
    import uuid
    from datetime import datetime

    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")

    # ── RBAC check — case-insensitive, accepts 'admin' and 'master' ──────────
    # The role value stored in the DB and minted into the JWT is lowercase
    # (e.g., 'admin'). We normalise to lowercase before comparison so that
    # a JWT issued with any casing variant ('Admin', 'ADMIN') still passes.
    # 'master' users are the tenant super-admins and must also be allowed.
    allowed_roles = {"admin", "master"}
    if current_user.role.lower() not in allowed_roles:
        print(
            f"{timestamp} [RBAC] nuke-tenant-data denied: "
            f"user={current_user.id} role={current_user.role!r}",
            flush=True
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem higienizar dados de testes."
        )

    tenant_uuid = uuid.UUID(str(current_user.tenant_id))
    print(f"{timestamp} ADMIN NUKE: Starting data cleaning for tenant_id {tenant_uuid}", flush=True)

    try:
        # PROTECTION: ClientPreference table is EXCLUDED from deletion
        # to ensure client preferences/memory survive nuke operations.
        from backend.models import AuditLog, OrderItem, PurchaseOrder

        # 1. Delete all AuditLogs for OrderItems of this tenant
        deleted_logs = db.query(AuditLog).filter(
            AuditLog.item_id.in_(
                db.query(OrderItem.id).filter(OrderItem.tenant_id == tenant_uuid)
            )
        ).delete(synchronize_session=False)

        # 2. Delete all OrderItems belonging to this tenant
        deleted_items = db.query(OrderItem).filter(
            OrderItem.tenant_id == tenant_uuid
        ).delete(synchronize_session=False)

        # 3. Delete all PurchaseOrders belonging to this tenant
        deleted_pos = db.query(PurchaseOrder).filter(
            PurchaseOrder.tenant_id == tenant_uuid
        ).delete(synchronize_session=False)

        db.commit()

        success_msg = (
            f"{timestamp} ADMIN NUKE SUCCESS: Cleared {deleted_logs} AuditLogs, "
            f"{deleted_items} OrderItems, and {deleted_pos} PurchaseOrders "
            f"for tenant {tenant_uuid} by user {current_user.id} ({current_user.role})"
        )
        print(success_msg, flush=True)
        return {
            "success": True,
            "message": "Banco de dados higienizado com sucesso!",
            "details": {
                "deleted_audit_logs": deleted_logs,
                "deleted_order_items": deleted_items,
                "deleted_purchase_orders": deleted_pos
            }
        }
    except Exception as exc:
        db.rollback()
        error_msg = f"{timestamp} ADMIN NUKE ERROR: Failed for tenant {tenant_uuid}: {str(exc)}"
        print(error_msg, flush=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao higienizar banco: {str(exc)}"
        )



class ApprovePartitionBody(BaseModel):
    freight_c1: float
    freight_c2: float

@router.post("/pos/{po_id}/approve-partition")
async def approve_partition(
    po_id: str,
    body: ApprovePartitionBody,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Commercial approves the partition by manually allocating freight split.
    """
    import uuid
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {po_id} não encontrado"
        )
        
    if po.status_macro != "WAITING_COMMERCIAL_PARTITION":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pedido não está aguardando partição. Status atual: {po.status_macro}"
        )
        
    children = db.query(PurchaseOrder).filter(
        PurchaseOrder.parent_po_id == po.id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).order_by(PurchaseOrder.created_at).all()
    
    if len(children) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este pedido não possui filhos criados para aprovar a partição"
        )
        
    # High-Precision Decimals check (4 decimal places)
    parent_freight = float(po.shipping_cost or 0)
    if parent_freight == 0 and po.items:
        first_item = po.items[0]
        if first_item.extra_metadata:
            meta_freight = first_item.extra_metadata.get("freight") or first_item.extra_metadata.get("Freight")
            if meta_freight:
                try:
                    parent_freight = float(meta_freight)
                except ValueError:
                    pass
        if parent_freight > 0:
            po.shipping_cost = parent_freight

    split_sum = body.freight_c1 + body.freight_c2
    
    # Apply high-precision freight splits
    children[0].shipping_cost = round(body.freight_c1, 4)
    children[1].shipping_cost = round(body.freight_c2, 4)
    
    # Move parent PO to ARCHIVED_PARTITIONED
    from_status = po.status_macro
    po.status_macro = "ARCHIVED_PARTITIONED"
    po.updated_at = datetime.utcnow()
    
    # Move children to SHIPPING (Expedição) for freight update - Zigue-Zague flow
    from sqlalchemy.orm.attributes import flag_modified
    for child in children:
        child.status_macro = "SHIPPING"
        child.partition_reason = None
        child.updated_at = datetime.utcnow()
        meta = dict(child.partition_metadata or {})
        meta["original_parent_freight"] = parent_freight
        meta["current_phase"] = "FASE_A"
        # Delete keys to kill the Awaiting Decision stamp
        if "suggested_delivery_date" in meta:
            del meta["suggested_delivery_date"]
        if "partition_reason" in meta:
            del meta["partition_reason"]
        child.partition_metadata = meta
        flag_modified(child, "partition_metadata")
        
    # Log parent transition
    log_po_status_transition(
        db=db,
        po=po,
        from_status=from_status,
        to_status="ARCHIVED_PARTITIONED",
        current_user=current_user,
        justification="Partição aprovada pelo comercial. Pedido pai arquivado.",
        extra_data={"action_type": "APPROVE_PARTITION_PARENT"}
    )
    
    # Log children transitions
    for child in children:
        log_po_status_transition(
            db=db,
            po=child,
            from_status="WAITING_COMMERCIAL_PARTITION",
            to_status="SHIPPING",
            current_user=current_user,
            justification=f"Partição criada a partir de {po.po_number}. Movido para Expedição (Ajuste de Frete).",
            extra_data={"action_type": "APPROVE_PARTITION_CHILD", "parent_po_number": po.po_number}
        )
        
    db.commit()
    
    return {
        "success": True,
        "message": "Partição aprovada com sucesso",
        "parent_po_id": po_id,
        "child1": {"id": str(children[0].id), "po_number": children[0].po_number, "freight": float(children[0].shipping_cost)},
        "child2": {"id": str(children[1].id), "po_number": children[1].po_number, "freight": float(children[1].shipping_cost)}
    }

class AllocateFreightBody(BaseModel):
    freight_c1: float
    freight_c2: float

@router.post("/pos/{po_id}/allocate-freight")
async def allocate_freight(
    po_id: str,
    body: AllocateFreightBody,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Expedição allocates/confirms the freight split and advances the child PO.
    """
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {po_id} não encontrado"
        )
        
    if not po.parent_po_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este pedido não é um lote particionado"
        )
        
    # Get all sibling children of the parent PO
    children = db.query(PurchaseOrder).filter(
        PurchaseOrder.parent_po_id == po.parent_po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).order_by(PurchaseOrder.created_at).all()
    
    if len(children) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Não foram encontrados os lotes filhos da partição"
        )
        
    # Verify that the sum matches the parent's original freight (if parent has freight)
    parent = db.query(PurchaseOrder).filter(PurchaseOrder.id == po.parent_po_id).first()
    parent_freight = float(parent.shipping_cost or 0) if parent else 0.0
    if parent_freight == 0 and parent and parent.items:
        first_item = parent.items[0]
        if first_item.extra_metadata:
            meta_freight = first_item.extra_metadata.get("freight") or first_item.extra_metadata.get("Freight")
            if meta_freight:
                try:
                    parent_freight = float(meta_freight)
                except ValueError:
                    pass
                    
    split_sum = body.freight_c1 + body.freight_c2
    
    # Apply freight splits to the children
    children[0].shipping_cost = round(body.freight_c1, 4)
    children[1].shipping_cost = round(body.freight_c2, 4)
    
    # Reassign to trigger JSONB mutation update on parent metadata if necessary
    if parent:
        parent.partition_metadata = dict(parent.partition_metadata or {})
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(parent, "partition_metadata")
    
    # Advance both children from SHIPPING to APPROVED (PCP stage)
    for child in children:
        if child.status_macro == "SHIPPING":
            from_status = child.status_macro
            child.status_macro = "APPROVED"
            child.updated_at = datetime.utcnow()
            
            # Set freight allocated flag on child
            meta = dict(child.partition_metadata or {})
            meta["freight_allocated"] = True
            meta["current_phase"] = "FASE_B"
            child.partition_metadata = meta
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(child, "partition_metadata")
            
            # Log transition
            log_po_status_transition(
                db=db,
                po=child,
                from_status=from_status,
                to_status="APPROVED",
                current_user=current_user,
                justification="CONFERIDO FRETE",
                extra_data={"action_type": "ALLOCATE_FREIGHT_CHILD", "freight_c1": body.freight_c1, "freight_c2": body.freight_c2}
            )
            
    db.commit()
    return {
        "success": True,
        "message": "Frete rateado e confirmado com sucesso. Lotes enviados para PCP."
    }


@router.post("/pos/{po_id}/pause-material")
async def pause_material(
    po_id: str,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Pause the SLA of the PO by setting it to WAITING_MATERIAL and recording sla_paused_at.
    """
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {po_id} não encontrado"
        )
        
    from_status = po.status_macro
    po.status_macro = "WAITING_MATERIAL"
    po.sla_paused_at = datetime.utcnow()
    po.updated_at = datetime.utcnow()
    
    # Delete any draft Child POs (C1/C2) and their OrderItems created during suggestion phase
    children = db.query(PurchaseOrder).filter(
        PurchaseOrder.parent_po_id == po.id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).all()
    for child in children:
        db.query(OrderItem).filter(OrderItem.po_id == child.id).delete(synchronize_session=False)
        db.delete(child)

    # Log status transition
    log_po_status_transition(
        db=db,
        po=po,
        from_status=from_status,
        to_status="WAITING_MATERIAL",
        current_user=current_user,
        justification="Aguardar Insumo.",
        extra_data={"action_type": "PAUSE_MATERIAL"}
    )
    
    db.commit()
    db.refresh(po)
    
    return {
        "success": True,
        "message": "Pedido pausado (Aguardando Insumo) com sucesso",
        "po_id": po_id,
        "status": po.status_macro
    }


@router.post("/pos/{po_id}/resume-material")
async def resume_material(
    po_id: str,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Resume the SLA of the PO, updating hold duration delta and logging in AuditLog.
    """
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {po_id} não encontrado"
        )
        
    if po.status_macro != "WAITING_MATERIAL":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pedido não está em pausa de material. Status atual: {po.status_macro}"
        )
        
    now = datetime.utcnow()
    paused_at = po.sla_paused_at
    hold_seconds = 0
    
    if paused_at:
        # If timezone-aware vs timezone-naive, make them naive
        p_at = paused_at.replace(tzinfo=None) if paused_at.tzinfo else paused_at
        hold_seconds = int((now - p_at).total_seconds())
        po.total_hold_time_seconds = (po.total_hold_time_seconds or 0) + hold_seconds
        
    po.sla_paused_at = None
    from_status = po.status_macro
    po.status_macro = "APPROVED" # Move back to PCP (APPROVED)
    po.updated_at = now
    
    # Calculate formatted duration for justification
    total_held = po.total_hold_time_seconds or 0
    # Current pause duration formatting
    cur_held = hold_seconds
    
    hrs = cur_held // 3600
    mins = (cur_held % 3600) // 60
    secs = cur_held % 60
    
    duration_str = ""
    if hrs > 0:
        duration_str += f"{hrs}h "
    if mins > 0 or hrs > 0:
        duration_str += f"{mins}m "
    duration_str += f"{secs}s"
    
    justification = f"SLA em curso. Insumo recebido após {duration_str.strip()}."
    
    # Log status transition
    log_po_status_transition(
        db=db,
        po=po,
        from_status=from_status,
        to_status="APPROVED",
        current_user=current_user,
        justification=justification,
        extra_data={
            "action_type": "RESUME_MATERIAL",
            "hold_seconds": cur_held,
            "total_hold_seconds": total_held,
            "duration_formatted": duration_str.strip()
        }
    )
    
    db.commit()
    
    return {
        "success": True,
        "message": "SLA retomado com sucesso",
        "po_id": po_id,
        "status": po.status_macro,
        "justification": justification
    }


@router.post("/pos/{po_id}/upload-cargo-photo")
async def upload_cargo_photo(
    po_id: str,
    file: UploadFile = File(..., description="Cargo photo (JPG, PNG)"),
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    print("STEP 1: Request received at backend", flush=True)
    print(f"STEP 2: File name received: {file.filename}", flush=True)

    # Query PO
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()

    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {po_id} não encontrado"
        )

    # Save file using GCSService
    from backend.services.gcs_service import GCSService, get_safe_filename
    from sqlalchemy.orm.attributes import flag_modified
    gcs_service = GCSService()
    print("STEP 3: Calling GCS Service...", flush=True)
    saved_path, attachment_filename = await gcs_service.upload_file(file, po_id)
    file_path = saved_path

    # Sanitize the filename using PureWindowsPath-backed helper to guard against
    # Windows browsers sending full paths like C:\Users\John\file.jpg
    safe_filename = get_safe_filename(file.filename) if file.filename else attachment_filename

    # Force a print log
    print(f"DEBUG: Saving GCS file to {file_path}")

    # ── PurchaseOrder.partition_metadata update ──────────────────────────────
    meta = dict(po.partition_metadata or {})
    meta['foto_carga_path'] = file_path

    # Check if logistics_checklist is None or missing, and initialize it
    if meta.get("logistics_checklist") is None:
        meta["logistics_checklist"] = {
            "endereco_conferido": False,
            "peso_validado": False,
            "etiquetas_impressas": False,
            "foto_carga_path": None,
            "foto_canhoto_path": None
        }

    logistics = dict(meta["logistics_checklist"])
    logistics['foto_carga_path'] = file_path
    logistics['updated_by'] = str(current_user.id)
    logistics['updated_at'] = datetime.utcnow().isoformat()
    meta['logistics_checklist'] = logistics

    po.partition_metadata = meta
    po.updated_at = datetime.utcnow()

    db.add(po)
    flag_modified(po, "partition_metadata")

    # ── OrderItem.extra_metadata["attachments"] persistence (FF-HARDENING-001) ─
    # SQLAlchemy does NOT auto-detect in-place JSONB mutations; flag_modified is
    # mandatory to ensure the appended attachment entry is committed to PostgreSQL.
    item = db.query(OrderItem).filter(OrderItem.po_id == po_id).first()
    if item is not None:
        if not item.extra_metadata:
            item.extra_metadata = {}

        if "attachments" not in item.extra_metadata:
            item.extra_metadata["attachments"] = []

        item.extra_metadata["attachments"].append({
            "filename": safe_filename,
            "url": file_path,
            "type": "cargo_photo",
            "timestamp": datetime.utcnow().isoformat()
        })

        # Explicitly mark the JSONB field as modified so SQLAlchemy flushes it
        flag_modified(item, "extra_metadata")
        db.add(item)

    db.commit()
    db.refresh(po)

    is_privileged = current_user.role.lower() in ["admin", "master"]
    mapped_po = _map_single_po(po, db, is_privileged)
    return {"success": True, "po": mapped_po}


@router.post("/pos/{po_id}/upload-receipt-photo")
async def upload_receipt_photo(
    po_id: str,
    file: UploadFile = File(..., description="Receipt/canhoto photo (JPG, PNG)"),
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Query PO
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()

    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido {po_id} não encontrado"
        )

    # Save file using GCSService
    from backend.services.gcs_service import GCSService, get_safe_filename
    from sqlalchemy.orm.attributes import flag_modified
    gcs_service = GCSService()
    saved_path, attachment_filename = await gcs_service.upload_file(file, po_id)
    file_path = saved_path

    # Sanitize the filename using PureWindowsPath-backed helper to guard against
    # Windows browsers sending full paths like C:\Users\John\file.jpg
    safe_filename = get_safe_filename(file.filename) if file.filename else attachment_filename

    # Force a print log
    print(f"DEBUG: Saving GCS file to {file_path}")

    # ── PurchaseOrder.partition_metadata update ──────────────────────────────
    meta = dict(po.partition_metadata or {})
    meta['foto_canhoto_path'] = file_path

    # Check if logistics_checklist is None or missing, and initialize it
    if meta.get("logistics_checklist") is None:
        meta["logistics_checklist"] = {
            "endereco_conferido": False,
            "peso_validado": False,
            "etiquetas_impressas": False,
            "foto_carga_path": None,
            "foto_canhoto_path": None
        }

    logistics = dict(meta["logistics_checklist"])
    logistics['foto_canhoto_path'] = file_path
    logistics['updated_by'] = str(current_user.id)
    logistics['updated_at'] = datetime.utcnow().isoformat()
    meta['logistics_checklist'] = logistics

    po.partition_metadata = meta
    po.updated_at = datetime.utcnow()

    db.add(po)
    flag_modified(po, "partition_metadata")

    # ── OrderItem.extra_metadata["attachments"] persistence (FF-HARDENING-001) ─
    # SQLAlchemy does NOT auto-detect in-place JSONB mutations; flag_modified is
    # mandatory to ensure the appended attachment entry is committed to PostgreSQL.
    item = db.query(OrderItem).filter(OrderItem.po_id == po_id).first()
    if item is not None:
        if not item.extra_metadata:
            item.extra_metadata = {}

        if "attachments" not in item.extra_metadata:
            item.extra_metadata["attachments"] = []

        item.extra_metadata["attachments"].append({
            "filename": safe_filename,
            "url": file_path,
            "type": "receipt_photo",
            "timestamp": datetime.utcnow().isoformat()
        })

        # Explicitly mark the JSONB field as modified so SQLAlchemy flushes it
        flag_modified(item, "extra_metadata")
        db.add(item)

    db.commit()
    db.refresh(po)

    is_privileged = current_user.role.lower() in ["admin", "master"]
    mapped_po = _map_single_po(po, db, is_privileged)
    return {"success": True, "po": mapped_po}


# ============================================================================
# FF-HARDENING-006: SLA Justification Endpoint
# ============================================================================

@router.post(
    "/pos/{po_id}/sla-justification",
    response_model=SlaJustificationResponse,
    status_code=status.HTTP_200_OK,
)
async def save_sla_justification(
    po_id: str,
    payload: SlaJustificationRequest,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Save an SLA failure-mode justification on any Purchase Order card.

    Business rules (FF-HARDENING-006):
    - Visible and editable on ALL PO cards regardless of SLA status.
    - Saving a justification NEVER pauses or modifies the SLA chronometer.
    - Auto-populates sla_justification_user (email) and sla_justification_at (UTC now).
    - Writes an immutable SHA-256 audit log entry with action 'SLA_JUSTIFICADO'.
    """
    from backend.models import AuditLog, get_last_audit_hash

    # ── 1. Resolve PO ──────────────────────────────────────────────────────────
    try:
        po_uuid = uuid.UUID(po_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase Order não encontrado.")

    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_uuid,
        PurchaseOrder.tenant_id == current_user.tenant_id,
    ).first()

    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase Order não encontrado.")

    # ── 2. Save justification fields (NEVER touches sla_paused_at / total_hold_time_seconds) ─
    now_utc = datetime.utcnow()
    po.sla_justification_category = payload.sla_justification_category
    po.sla_justification_text     = payload.sla_justification_text or None
    po.sla_justification_user     = current_user.email
    po.sla_justification_at       = now_utc
    po.updated_at                 = now_utc

    # ── 3. Immutable audit log — SHA-256 ledger entry (action: SLA_JUSTIFICADO) ─
    # AuditLog.item_id is FK→order_items; we use the first item of the PO.
    # If the PO somehow has no items, we skip the audit log (non-fatal) and note it.
    audit_hash = "N/A"
    if po.items:
        first_item = po.items[0]
        changed_by_uuid = uuid.UUID(str(current_user.id)) if current_user.id else None
        previous_hash   = get_last_audit_hash(db, first_item.id)

        audit_hash = AuditLog.calculate_hash_for_version(
            version=AuditLog.HASH_VERSION_CURRENT,
            tenant_id=po.tenant_id,
            item_id=first_item.id,
            from_status=po.status_macro,     # SLA justification does NOT change status
            to_status=po.status_macro,        # same value — status is unchanged
            timestamp=now_utc,
            previous_hash=previous_hash,
            changed_by=changed_by_uuid,
        )

        audit_entry = AuditLog(
            item_id=first_item.id,
            from_status=po.status_macro,
            to_status=po.status_macro,
            hash=audit_hash,
            previous_hash=previous_hash,
            hash_version=AuditLog.HASH_VERSION_CURRENT,
            is_exception=False,
            justification=payload.sla_justification_text,
            changed_by=changed_by_uuid,
            extra_data={
                "action":                    "SLA_JUSTIFICADO",
                "po_id":                     str(po.id),
                "po_number":                 po.po_number,
                "sla_justification_category": payload.sla_justification_category,
                "sla_justification_text":    payload.sla_justification_text or "",
                "sla_justification_user":    current_user.email,
                "sla_justification_at":      now_utc.isoformat(),
                "user_role":                 current_user.role,
                "sla_chronometer_paused":    False,   # immutable business rule marker
            },
        )
        db.add(audit_entry)
    else:
        print(
            f"[SLA-JUSTIFICATION] WARNING: PO {po_id} has no items — "
            "skipping audit log entry (justification fields still saved)."
        )

    # ── 4. Persist ─────────────────────────────────────────────────────────────
    try:
        db.commit()
        db.refresh(po)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Falha ao salvar justificativa SLA: {str(exc)}",
        ) from exc

    print(
        f"[SLA-JUSTIFICATION] PO={po.po_number} | "
        f"Category={po.sla_justification_category} | "
        f"User={po.sla_justification_user} | "
        f"AuditHash={audit_hash[:16]}..."
    )

    return SlaJustificationResponse(
        success=True,
        message=f"Justificativa SLA salva com sucesso para o pedido {po.po_number}.",
        po_id=str(po.id),
        sla_justification_category=po.sla_justification_category,
        sla_justification_text=po.sla_justification_text,
        sla_justification_user=po.sla_justification_user,
        sla_justification_at=po.sla_justification_at,
        audit_hash=audit_hash,
    )


# ─────────────────────────────────────────────────────────────────────────────
# FF-HARDENING-012.2 [Item 2]: Invoice PDF Upload — Faturamento Stage
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/pos/{po_id}/upload-invoice-pdf")
async def upload_invoice_pdf(
    po_id: str,
    file: UploadFile = File(..., description="Invoice PDF or image (PDF, JPG, PNG)"),
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload the Faturamento NF-e document for a PO.
    Saves GCS path to partition_metadata.invoice_pdf_path.
    NOTE: PurchaseOrder has no extra_metadata column — all PO-level metadata
    lives in partition_metadata (JSONB). The frontend mapper exposes
    partition_metadata as selectedPO.extra_metadata, so frontend reads are
    already correct."""
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pedido {po_id} não encontrado")

    from backend.services.gcs_service import GCSService, get_safe_filename
    from sqlalchemy.orm.attributes import flag_modified

    gcs_service = GCSService()
    saved_path, attachment_filename = await gcs_service.upload_file(file, po_id)
    safe_filename = get_safe_filename(file.filename) if file.filename else attachment_filename
    print(f"[INVOICE-PDF] PO={po.po_number} | GCS path={saved_path}")

    # PurchaseOrder stores all metadata in partition_metadata (JSONB).
    # The frontend mapper returns partition_metadata as selectedPO.extra_metadata,
    # so selectedPO.extra_metadata.invoice_pdf_path resolves correctly in the UI.
    pmeta = dict(po.partition_metadata or {})
    pmeta["invoice_pdf_path"] = saved_path
    pmeta["invoice_pdf_filename"] = safe_filename
    pmeta["invoice_pdf_uploaded_by"] = str(current_user.id)
    pmeta["invoice_pdf_uploaded_at"] = datetime.utcnow().isoformat()
    po.partition_metadata = pmeta
    po.updated_at = datetime.utcnow()
    db.add(po)
    flag_modified(po, "partition_metadata")  # mandatory: tells SQLAlchemy the JSONB dict changed
    db.commit()
    db.refresh(po)

    is_privileged = current_user.role.lower() in ["admin", "master"]
    mapped_po = _map_single_po(po, db, is_privileged)
    return {"success": True, "invoice_pdf_path": saved_path, "invoice_pdf_filename": safe_filename, "po": mapped_po}



# ─────────────────────────────────────────────────────────────────────────────
# FF-HARDENING-012.3 [Item 2]: Upload Invoice XML for Faturamento stage
# Stores path in extra_metadata.invoice_xml_path.
# Either PDF or XML satisfies the dispatch guardrail (at least one required).
# ─────────────────────────────────────────────────────────────────────────────
@router.post("/pos/{po_id}/upload-invoice-xml")
async def upload_invoice_xml(
    po_id: str,
    file: UploadFile = File(..., description="Invoice PDF (secondary slot) or image"),
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload the secondary Faturamento document (PDF Secundário) for a PO.
    Saves GCS path to partition_metadata.invoice_xml_path.
    NOTE: Despite the endpoint name containing 'xml', this slot accepts PDF/images
    and is displayed as 'NF-e PDF Secundário' in the UI. The path key
    invoice_xml_path is kept for backward DB compatibility."""
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pedido {po_id} nao encontrado")

    from backend.services.gcs_service import GCSService, get_safe_filename
    from sqlalchemy.orm.attributes import flag_modified

    gcs_service = GCSService()
    saved_path, attachment_filename = await gcs_service.upload_file(file, po_id)
    safe_filename = get_safe_filename(file.filename) if file.filename else attachment_filename
    print(f"[INVOICE-XML] PO={po.po_number} | GCS path={saved_path}")

    # PurchaseOrder stores all metadata in partition_metadata (JSONB).
    pmeta = dict(po.partition_metadata or {})
    pmeta["invoice_xml_path"] = saved_path
    pmeta["invoice_xml_filename"] = safe_filename
    pmeta["invoice_xml_uploaded_by"] = str(current_user.id)
    pmeta["invoice_xml_uploaded_at"] = datetime.utcnow().isoformat()
    po.partition_metadata = pmeta
    po.updated_at = datetime.utcnow()
    db.add(po)
    flag_modified(po, "partition_metadata")  # mandatory: tells SQLAlchemy the JSONB dict changed
    db.commit()
    db.refresh(po)

    is_privileged = current_user.role.lower() in ["admin", "master"]
    mapped_po = _map_single_po(po, db, is_privileged)
    return {"success": True, "invoice_xml_path": saved_path, "invoice_xml_filename": safe_filename, "po": mapped_po}


# ─────────────────────────────────────────────────────────────────────────────
# FF-HARDENING-012.2 [Item 3]: Create Manual Exchange/Return Card
# tenant_id is always extracted from current_user — never accepted from body.
# ─────────────────────────────────────────────────────────────────────────────
class ExchangeCardRequest(BaseModel):
    po_original: str  # [9.3] mandatory original PO ref; card named TR-[po_original]
    cliente: str
    produto: str
    quantidade: float
    unidade_medida: str
    largura: Optional[float] = None
    comprimento: Optional[float] = None

    @validator("po_original")
    def po_original_not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Nº da PO Original é obrigatório")
        return v.strip()

    @validator("cliente", "produto")
    def not_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("Campo obrigatório não pode estar vazio")
        return v.strip()

    @validator("unidade_medida")
    def valid_unit(cls, v):
        allowed = {"M2", "KG", "UN"}
        if v.upper() not in allowed:
            raise ValueError(f"Unidade de medida deve ser um de: {', '.join(allowed)}")
        return v.upper()

    @validator("quantidade")
    def positive_qty(cls, v):
        if v <= 0:
            raise ValueError("Quantidade deve ser maior que zero")
        return v


@router.post("/exchange-cards")
async def create_exchange_card(
    request: ExchangeCardRequest,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a manual Troca/Devoluçao PO in the Comercial column.
    tenant_id is always from current_user to prevent cross-tenant data leaks.
    """
    import uuid as _uuid
    # UAT-FIX-1: Import Decimal early — needed for both PO and OrderItem Numeric fields
    from decimal import Decimal as _Decimal

    # UAT-FIX-3: PO number uses original PO reference (9.3) + SLA 50% flag (9.1)
    po_number = f"TR-{request.po_original.strip()}"

    new_po = PurchaseOrder(
        id=_uuid.uuid4(),
        tenant_id=current_user.tenant_id,
        po_number=po_number,
        status_macro="SUBMITTED",
        created_by=current_user.id,
        shipping_cost=_Decimal('0'),
        is_partitioned=False,
        partition_metadata={"client_name": request.cliente},
    )
    db.add(new_po)
    db.flush()

    sku_code = request.produto[:50].upper().replace(" ", "_")
    # UAT-FIX-1: Convert float inputs to Decimal to avoid TypeError with Numeric DB columns
    _qty = _Decimal(str(request.quantidade))
    _largura = _Decimal(str(request.largura)) if request.largura is not None else None
    _comprimento = _Decimal(str(request.comprimento)) if request.comprimento is not None else None

    new_item = OrderItem(
        id=_uuid.uuid4(),
        po_id=new_po.id,
        tenant_id=current_user.tenant_id,
        sku=sku_code,
        quantity=_qty,
        price=_Decimal('0'),
        status_item="PENDING",
        is_personalized=False,
        is_new_client=False,
        extra_metadata={
            "is_exchange_return": True,
            "po_original": request.po_original.strip(),  # [9.3] Original PO reference
            "sla_50pct": True,                           # [9.1] Flag for 50% SLA reduction
            "client_name": request.cliente,
            "description": request.produto,
            "unit": request.unidade_medida,
            "largura": str(_largura) if _largura is not None else None,
            "comprimento": str(_comprimento) if _comprimento is not None else None,
            "created_by_name": getattr(current_user, "name", str(current_user.id)),
            "created_at_manual": datetime.utcnow().isoformat(),
        },
    )
    db.add(new_item)

    try:
        db.commit()
        db.refresh(new_po)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar card de troca/devolucao: {str(exc)}"
        ) from exc

    is_privileged = current_user.role.lower() in ["admin", "master"]
    mapped_po = _map_single_po(new_po, db, is_privileged)
    return {
        "success": True,
        "message": f"Card de Troca/Devolucao '{po_number}' criado com sucesso no Comercial.",
        "po_number": po_number,
        "po": mapped_po
    }
