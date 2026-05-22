"""
FlexFlow Kanban Router
Endpoints for Kanban board operations and status management.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal
from datetime import datetime

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
    UpdateLogisticsChecklistResponse
)
from backend.schemas.auth_schema import UserInfo
from backend.database import get_db
from backend.routers.auth import get_current_user
from backend.models import PurchaseOrder, OrderItem

router = APIRouter(prefix="/api/kanban", tags=["Kanban"])


# Status mapping: Database status -> Display name (Portuguese)
# Official Process Blueprint V2.0 - 5 Column Structure
STATUS_DISPLAY_MAP = {
    "DRAFT": "Comercial",
    "SUBMITTED": "Comercial",  # SUBMITTED now shows in Comercial
    "WAITING_COMMERCIAL_PARTITION": "Comercial",  # Shows in Comercial with purple badge
    "APPROVED": "PCP",
    "IN_PROGRESS": "Produção/Embalagem",
    "WAITING_DISPATCH": "Faturamento/Expedição",
    "AUDIT_PENDING": "Financeiro",
    "COMPLETED": "Financeiro",
    "ANALISE_CREDITO": "Financeiro",
    "CANCELLED": "Cancelado"
}

# Reverse mapping for API compatibility
DISPLAY_TO_DB_STATUS = {v: k for k, v in STATUS_DISPLAY_MAP.items()}

# Status flow for bidirectional movement - Official Process Blueprint V2.0
STATUS_FLOW = {
    "DRAFT": {"next": "SUBMITTED", "prev": None},
    "SUBMITTED": {"next": "APPROVED", "prev": "DRAFT"},
    "WAITING_COMMERCIAL_PARTITION": {"next": "APPROVED", "prev": None},
    "APPROVED": {"next": "IN_PROGRESS", "prev": "SUBMITTED"},
    "IN_PROGRESS": {"next": "WAITING_DISPATCH", "prev": "APPROVED"},
    "WAITING_DISPATCH": {"next": "AUDIT_PENDING", "prev": "IN_PROGRESS"},
    "AUDIT_PENDING": {"next": "COMPLETED", "prev": "WAITING_DISPATCH"},
    "COMPLETED": {"next": None, "prev": "AUDIT_PENDING"}
}


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
    
    # Query database for POs
    pos = db.query(PurchaseOrder).filter(
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).all()
    
    # Define status columns - Official Process Blueprint V2.0 (5 Columns)
    # Comercial: SUBMITTED or WAITING_COMMERCIAL_PARTITION
    # PCP: APPROVED
    # Produção/Embalagem: IN_PROGRESS
    # Faturamento/Expedição: WAITING_DISPATCH
    # Financeiro: AUDIT_PENDING or COMPLETED
    status_columns = [
        ("Comercial", ["SUBMITTED", "WAITING_COMMERCIAL_PARTITION"]),
        ("PCP", ["APPROVED"]),
        ("Produção/Embalagem", ["IN_PROGRESS"]),
        ("Faturamento/Expedição", ["WAITING_DISPATCH"]),
        ("Financeiro", ["AUDIT_PENDING", "COMPLETED", "ANALISE_CREDITO"])
    ]
    
    # Group POs by status
    columns = []
    for display_name, db_statuses in status_columns:
        # Filter POs for this column (may include multiple statuses)
        status_pos = [po for po in pos if po.status_macro in db_statuses]
        
        # Convert to response models
        po_responses = []
        for po in status_pos:
            # Calculate metrics
            metrics = calculate_po_metrics(po)
            
            # Convert items
            items = [
                POItemResponse(
                    id=str(item.id),
                    sku=item.sku,
                    quantity=item.quantity,
                    price=Decimal(str(item.price)),
                    status_item=item.status_item,
                    margin_item=Decimal("0.00"),  # Calculate if needed
                    total_cost=Decimal("0.00"),  # Calculate if needed
                    manual_commission_rate=Decimal(str(item.extra_metadata.get("manual_commission_rate"))) if item.extra_metadata and "manual_commission_rate" in item.extra_metadata else None,
                    extra_metadata=item.extra_metadata,
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in po.items
            ]
            
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
            
            po_response = POResponse(
                id=str(po.id),
                po_number=po.po_number,
                client_name=getattr(po, 'client_name', None) or "Cliente Desconhecido",
                supplier_name=getattr(po, 'client_name', None) or "Fornecedor Desconhecido",
                status_macro=display_name,  # Use display name
                status=display_name,  # Alias for frontend compatibility
                items=items,
                items_count=len(items),
                total_value=metrics["total_value"],
                margin_global=metrics["margin_global"],
                margin_percentage=metrics["margin_percentage"],
                commission_rate=commission_rate,
                commission_value=commission_value,
                shipping_cost=Decimal(str(po.shipping_cost)),
                expected_delivery_date=getattr(po, 'expected_delivery_date', None),
                priority=getattr(po, 'priority', 'normal'),
                extra_metadata=po.partition_metadata,
                logistics_checklist=logistics_checklist,
                created_at=po.created_at,
                updated_at=po.updated_at,
                created_by=str(po.created_by) if po.created_by else None
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
    pos = query.offset(skip).limit(limit).all()
    
    # Convert to response models
    po_responses = []
    for po in pos:
        metrics = calculate_po_metrics(po)
        
        items = [
            POItemResponse(
                id=str(item.id),
                sku=item.sku,
                quantity=item.quantity,
                price=Decimal(str(item.price)),
                status_item=item.status_item,
                margin_item=Decimal("0.00"),
                total_cost=Decimal("0.00"),
                manual_commission_rate=Decimal(str(item.extra_metadata.get("manual_commission_rate"))) if item.extra_metadata and "manual_commission_rate" in item.extra_metadata else None,
                extra_metadata=item.extra_metadata,
                created_at=item.created_at,
                updated_at=item.updated_at
            )
            for item in po.items
        ]
        
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
            supplier_name=getattr(po, 'client_name', None) or "Fornecedor Desconhecido",
            status_macro=STATUS_DISPLAY_MAP.get(po.status_macro, po.status_macro),
            status=STATUS_DISPLAY_MAP.get(po.status_macro, po.status_macro),
            items=items,
            items_count=len(items),
            total_value=metrics["total_value"],
            margin_global=metrics["margin_global"],
            margin_percentage=metrics["margin_percentage"],
            commission_rate=commission_rate,
            commission_value=commission_value,
            shipping_cost=Decimal(str(po.shipping_cost)),
            expected_delivery_date=getattr(po, 'expected_delivery_date', None),
            priority=getattr(po, 'priority', 'normal'),
            extra_metadata=po.partition_metadata,
            logistics_checklist=logistics_checklist,
            created_at=po.created_at,
            updated_at=po.updated_at,
            created_by=str(po.created_by) if po.created_by else None
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
    
    # Calculate metrics
    metrics = calculate_po_metrics(po)
    
    # Convert items
    items = [
        POItemResponse(
            id=str(item.id),
            sku=item.sku,
            quantity=item.quantity,
            price=Decimal(str(item.price)),
            status_item=item.status_item,
            margin_item=Decimal("0.00"),
            total_cost=Decimal("0.00"),
            manual_commission_rate=Decimal(str(item.extra_metadata.get("manual_commission_rate"))) if item.extra_metadata and "manual_commission_rate" in item.extra_metadata else None,
            extra_metadata=item.extra_metadata,
            created_at=item.created_at,
            updated_at=item.updated_at
        )
        for item in po.items
    ]
    
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
    
    return POResponse(
        id=str(po.id),
        po_number=po.po_number,
        client_name=getattr(po, 'client_name', None) or "Cliente Desconhecido",
        supplier_name=getattr(po, 'client_name', None) or "Fornecedor Desconhecido",
        status_macro=STATUS_DISPLAY_MAP.get(po.status_macro, po.status_macro),
        status=STATUS_DISPLAY_MAP.get(po.status_macro, po.status_macro),
        items=items,
        items_count=len(items),
        total_value=metrics["total_value"],
        margin_global=metrics["margin_global"],
        margin_percentage=metrics["margin_percentage"],
        commission_rate=commission_rate,
        commission_value=commission_value,
        shipping_cost=Decimal(str(po.shipping_cost)),
        expected_delivery_date=getattr(po, 'expected_delivery_date', None),
        priority=getattr(po, 'priority', 'normal'),
        extra_metadata=po.partition_metadata,
        logistics_checklist=logistics_checklist,
        created_at=po.created_at,
        updated_at=po.updated_at,
        created_by=str(po.created_by) if po.created_by else None
    )


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
        "APPROVED": ["WAITING_DISPATCH", "SUBMITTED"],
        "WAITING_DISPATCH": ["COMPLETED", "APPROVED"],
        "COMPLETED": ["WAITING_DISPATCH"],  # Allow return for corrections
        "CANCELLED": [],
        "WAITING_COMMERCIAL_PARTITION": ["SUBMITTED"]
    }
    
    is_exception = False
    
    # Check if transition is valid
    if to_status_db not in valid_transitions.get(from_status, []):
        # Check if user can skip validation
        if request.skip_validation:
            # Verify user has LEADER or MASTER role
            if current_user.role not in ["LEADER", "MASTER"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Apenas usuários LEADER ou MASTER podem realizar salto de etapa"
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
    
    # Update status
    po.status_macro = to_status_db
    po.updated_at = datetime.utcnow()
    
    # Create audit log for exception if applicable
    if is_exception:
        from backend.models import AuditLog
        
        # Log the exception for each item in the PO
        for item in po.items:
            # Get previous hash for blockchain
            from backend.models import get_last_audit_hash
            previous_hash = get_last_audit_hash(db, item.id)
            
            # Calculate new hash
            audit_hash = AuditLog.calculate_hash(
                item_id=item.id,
                from_status=from_status,
                to_status=to_status_db,
                timestamp=datetime.utcnow(),
                previous_hash=previous_hash,
                changed_by=current_user.id
            )
            
            # Create audit log entry
            audit_entry = AuditLog(
                item_id=item.id,
                from_status=from_status,
                to_status=to_status_db,
                hash=audit_hash,
                previous_hash=previous_hash,
                is_exception=True,
                justification=request.justificativa_lider,
                changed_by=current_user.id,
                extra_data={
                    "po_id": str(po.id),
                    "po_number": po.po_number,
                    "user_role": current_user.role,
                    "reason": request.reason,
                    "metadata": request.metadata
                }
            )
            db.add(audit_entry)
    
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
    if current_user.role not in ["MASTER", "ADMIN"]:
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
    
    # Update commission rate in PO metadata
    if not po.partition_metadata:
        po.partition_metadata = {}
    
    po.partition_metadata["manual_commission_rate"] = float(request.manual_commission_rate)
    po.partition_metadata["commission_justification"] = request.justification
    po.partition_metadata["commission_updated_by"] = str(current_user.id)
    po.partition_metadata["commission_updated_at"] = datetime.utcnow().isoformat()
    
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
        
        # Update item's manual commission rate
        if not item.extra_metadata:
            item.extra_metadata = {}
        
        item.extra_metadata["manual_commission_rate"] = float(request.manual_commission_rate)
        item.extra_metadata["commission_justification"] = request.justification
        item.extra_metadata["commission_updated_by"] = str(current_user.id)
        item.extra_metadata["commission_updated_at"] = datetime.utcnow().isoformat()
    
    po.updated_at = datetime.utcnow()
    db.commit()
    
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
    
    # Update logistics checklist in metadata
    if not po.partition_metadata:
        po.partition_metadata = {}
    
    logistics_checklist = {
        "endereco_conferido": request.endereco_conferido,
        "peso_validado": request.peso_validado,
        "etiquetas_impressas": request.etiquetas_impressas,
        "foto_carga_path": request.foto_carga_path,
        "foto_canhoto_path": request.foto_canhoto_path,
        "updated_by": str(current_user.id),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    po.partition_metadata["logistics_checklist"] = logistics_checklist
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
    
    db.commit()
    
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
        can_dispatch=can_dispatch
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
        logistics_checklist = po.partition_metadata["logistics_checklist"]
    else:
        # Return default empty checklist
        logistics_checklist = {
            "endereco_conferido": False,
            "peso_validado": False,
            "etiquetas_impressas": False,
            "foto_carga_path": None,
            "foto_canhoto_path": None
        }
    
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
    
    elif current_status == "WAITING_DISPATCH":
        # Dispatch must have logistics checklist complete
        if po.partition_metadata and "logistics_checklist" in po.partition_metadata:
            checklist = po.partition_metadata["logistics_checklist"]
            if not all([
                checklist.get("endereco_conferido"),
                checklist.get("peso_validado"),
                checklist.get("etiquetas_impressas"),
                checklist.get("foto_carga_path"),
                checklist.get("foto_canhoto_path")
            ]):
                validation_errors.append("Checklist de logística deve estar completo")
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
    """
    if not reason or len(reason.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Motivo da devolução deve ter pelo menos 10 caracteres"
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
    
    # Create audit log for return
    from backend.models import AuditLog
    
    for item in po.items:
        # Get previous hash for blockchain
        from backend.models import get_last_audit_hash
        previous_hash = get_last_audit_hash(db, item.id)
        
        # Calculate new hash
        audit_hash = AuditLog.calculate_hash(
            item_id=item.id,
            from_status=from_status,
            to_status=prev_status,
            timestamp=datetime.utcnow(),
            previous_hash=previous_hash,
            changed_by=current_user.id
        )
        
        # Create audit log entry
        audit_entry = AuditLog(
            item_id=item.id,
            from_status=from_status,
            to_status=prev_status,
            hash=audit_hash,
            previous_hash=previous_hash,
            is_exception=False,
            justification=f"DEVOLUÇÃO: {reason}",
            changed_by=current_user.id,
            extra_data={
                "po_id": str(po.id),
                "po_number": po.po_number,
                "user_role": current_user.role,
                "return_reason": reason,
                "action_type": "RETURN"
            }
        )
        db.add(audit_entry)
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Pedido devolvido para {STATUS_DISPLAY_MAP.get(prev_status, prev_status)}",
        "po_id": po_id,
        "from_status": STATUS_DISPLAY_MAP.get(from_status, from_status),
        "to_status": STATUS_DISPLAY_MAP.get(prev_status, prev_status),
        "reason": reason
    }


@router.post("/suggest-partition")
async def suggest_partition(
    po_id: str,
    reason: str,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    PCP-specific action: Suggest partition and move PO back to Comercial
    with WAITING_COMMERCIAL_PARTITION status.
    """
    if not reason or len(reason.strip()) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Motivo da sugestão de partição deve ter pelo menos 10 caracteres"
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
    
    # Verify PO is in PCP stage
    if po.status_macro != "SUBMITTED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sugestão de partição só pode ser feita no estágio PCP"
        )
    
    # Update status to WAITING_COMMERCIAL_PARTITION
    from_status = po.status_macro
    po.status_macro = "WAITING_COMMERCIAL_PARTITION"
    po.partition_reason = reason
    po.updated_at = datetime.utcnow()
    
    # Create audit log
    from backend.models import AuditLog
    
    for item in po.items:
        from backend.models import get_last_audit_hash
        previous_hash = get_last_audit_hash(db, item.id)
        
        audit_hash = AuditLog.calculate_hash(
            item_id=item.id,
            from_status=from_status,
            to_status="WAITING_COMMERCIAL_PARTITION",
            timestamp=datetime.utcnow(),
            previous_hash=previous_hash,
            changed_by=current_user.id
        )
        
        audit_entry = AuditLog(
            item_id=item.id,
            from_status=from_status,
            to_status="WAITING_COMMERCIAL_PARTITION",
            hash=audit_hash,
            previous_hash=previous_hash,
            is_exception=False,
            justification=f"SUGESTÃO DE PARTIÇÃO: {reason}",
            changed_by=current_user.id,
            extra_data={
                "po_id": str(po.id),
                "po_number": po.po_number,
                "user_role": current_user.role,
                "partition_reason": reason,
                "action_type": "SUGGEST_PARTITION"
            }
        )
        db.add(audit_entry)
    
    db.commit()
    
    return {
        "success": True,
        "message": "Sugestão de partição enviada para Comercial",
        "po_id": po_id,
        "from_status": STATUS_DISPLAY_MAP.get(from_status, from_status),
        "to_status": STATUS_DISPLAY_MAP.get("WAITING_COMMERCIAL_PARTITION", "Aguardando Partição"),
        "reason": reason
    }
