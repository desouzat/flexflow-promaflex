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
    POFilterParams
)
from backend.schemas.auth_schema import UserInfo
from backend.database import get_db
from backend.routers.auth import get_current_user
from backend.models import PurchaseOrder, OrderItem

router = APIRouter(prefix="/api/kanban", tags=["Kanban"])


# Status mapping: Database status -> Display name (Portuguese)
STATUS_DISPLAY_MAP = {
    "DRAFT": "Pendente",
    "SUBMITTED": "PCP",
    "APPROVED": "Produção",
    "IN_PROGRESS": "Expedição",
    "COMPLETED": "Concluído",
    "CANCELLED": "Cancelado"
}

# Reverse mapping for API compatibility
DISPLAY_TO_DB_STATUS = {v: k for k, v in STATUS_DISPLAY_MAP.items()}


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
    
    # Define status columns (in Portuguese)
    status_columns = [
        ("DRAFT", "Pendente"),
        ("SUBMITTED", "PCP"),
        ("APPROVED", "Produção"),
        ("IN_PROGRESS", "Expedição"),
        ("COMPLETED", "Concluído")
    ]
    
    # Group POs by status
    columns = []
    for db_status, display_name in status_columns:
        # Filter POs for this status
        status_pos = [po for po in pos if po.status_macro == db_status]
        
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
                    created_at=item.created_at,
                    updated_at=item.updated_at
                )
                for item in po.items
            ]
            
            po_response = POResponse(
                id=str(po.id),
                po_number=po.po_number,
                client_name=getattr(po, 'client_name', None) or "Cliente",
                supplier_name=getattr(po, 'supplier_name', None) or getattr(po, 'client_name', None) or "Fornecedor Desconhecido",
                status_macro=display_name,  # Use display name
                status=display_name,  # Alias for frontend compatibility
                items=items,
                items_count=len(items),
                total_value=metrics["total_value"],
                margin_global=metrics["margin_global"],
                margin_percentage=metrics["margin_percentage"],
                expected_delivery_date=getattr(po, 'expected_delivery_date', None),
                priority=getattr(po, 'priority', 'normal'),
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
                created_at=item.created_at,
                updated_at=item.updated_at
            )
            for item in po.items
        ]
        
        po_response = POResponse(
            id=str(po.id),
            po_number=po.po_number,
            client_name=getattr(po, 'client_name', None) or "Cliente",
            supplier_name=getattr(po, 'supplier_name', None) or getattr(po, 'client_name', None) or "Fornecedor Desconhecido",
            status_macro=STATUS_DISPLAY_MAP.get(po.status_macro, po.status_macro),
            status=STATUS_DISPLAY_MAP.get(po.status_macro, po.status_macro),
            items=items,
            items_count=len(items),
            total_value=metrics["total_value"],
            margin_global=metrics["margin_global"],
            margin_percentage=metrics["margin_percentage"],
            expected_delivery_date=getattr(po, 'expected_delivery_date', None),
            priority=getattr(po, 'priority', 'normal'),
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
            created_at=item.created_at,
            updated_at=item.updated_at
        )
        for item in po.items
    ]
    
    return POResponse(
        id=str(po.id),
        po_number=po.po_number,
        client_name=getattr(po, 'client_name', None) or "Cliente",
        supplier_name=getattr(po, 'supplier_name', None) or getattr(po, 'client_name', None) or "Fornecedor Desconhecido",
        status_macro=STATUS_DISPLAY_MAP.get(po.status_macro, po.status_macro),
        status=STATUS_DISPLAY_MAP.get(po.status_macro, po.status_macro),
        items=items,
        items_count=len(items),
        total_value=metrics["total_value"],
        margin_global=metrics["margin_global"],
        margin_percentage=metrics["margin_percentage"],
        expected_delivery_date=getattr(po, 'expected_delivery_date', None),
        priority=getattr(po, 'priority', 'normal'),
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
    
    # Define valid transitions
    valid_transitions = {
        "DRAFT": ["SUBMITTED"],
        "SUBMITTED": ["APPROVED", "DRAFT"],
        "APPROVED": ["IN_PROGRESS"],
        "IN_PROGRESS": ["COMPLETED"],
        "COMPLETED": [],
        "CANCELLED": []
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
                changed_by=current_user.user_id
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
                changed_by=current_user.user_id,
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
