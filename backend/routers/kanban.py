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

router = APIRouter(prefix="/api/kanban", tags=["Kanban"])


# Mock data for demonstration (replace with database queries in production)
def get_mock_pos(tenant_id: str) -> List[dict]:
    """Generate mock PO data for demonstration"""
    return [
        {
            "id": "po-001",
            "po_number": "PO-2024-001",
            "client_name": "Acme Corp",
            "status_macro": "COMERCIAL",
            "total_value": Decimal("25000.00"),
            "margin_global": Decimal("8250.00"),
            "margin_percentage": Decimal("33.00"),
            "created_at": datetime(2024, 3, 1),
            "updated_at": datetime(2024, 3, 1),
            "created_by": "user-123",
            "items": [
                {
                    "id": "item-001",
                    "sku": "SKU-001",
                    "quantity": 100,
                    "price": Decimal("150.00"),
                    "status_item": "PENDING",
                    "margin_item": Decimal("55.00"),
                    "total_cost": Decimal("95.00"),
                    "created_at": datetime(2024, 3, 1),
                    "updated_at": datetime(2024, 3, 1)
                }
            ]
        },
        {
            "id": "po-002",
            "po_number": "PO-2024-002",
            "client_name": "Beta Industries",
            "status_macro": "PCP",
            "total_value": Decimal("50000.00"),
            "margin_global": Decimal("15000.00"),
            "margin_percentage": Decimal("30.00"),
            "created_at": datetime(2024, 3, 5),
            "updated_at": datetime(2024, 3, 10),
            "created_by": "user-123",
            "items": [
                {
                    "id": "item-002",
                    "sku": "SKU-002",
                    "quantity": 50,
                    "price": Decimal("200.00"),
                    "status_item": "ORDERED",
                    "margin_item": Decimal("65.00"),
                    "total_cost": Decimal("135.00"),
                    "created_at": datetime(2024, 3, 5),
                    "updated_at": datetime(2024, 3, 10)
                }
            ]
        },
        {
            "id": "po-003",
            "po_number": "PO-2024-003",
            "client_name": "Gamma Solutions",
            "status_macro": "PRODUCAO",
            "total_value": Decimal("75000.00"),
            "margin_global": Decimal("22500.00"),
            "margin_percentage": Decimal("30.00"),
            "created_at": datetime(2024, 3, 8),
            "updated_at": datetime(2024, 3, 15),
            "created_by": "user-456",
            "items": [
                {
                    "id": "item-003",
                    "sku": "SKU-003",
                    "quantity": 75,
                    "price": Decimal("300.00"),
                    "status_item": "RECEIVED",
                    "margin_item": Decimal("100.00"),
                    "total_cost": Decimal("200.00"),
                    "created_at": datetime(2024, 3, 8),
                    "updated_at": datetime(2024, 3, 15)
                }
            ]
        }
    ]


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
    
    # In production, query database:
    # pos = db.query(PurchaseOrder).filter(
    #     PurchaseOrder.tenant_id == current_user.tenant_id
    # ).all()
    
    # For demo, use mock data
    mock_pos = get_mock_pos(current_user.tenant_id)
    
    # Define status columns
    status_columns = [
        "COMERCIAL",
        "PCP",
        "PRODUCAO",
        "EXPEDICAO_PENDENTE",
        "FATURAMENTO_PENDENTE",
        "DESPACHO",
        "CONCLUIDO"
    ]
    
    # Group POs by status
    columns = []
    for status_name in status_columns:
        # Filter POs for this status
        status_pos = [po for po in mock_pos if po["status_macro"] == status_name]
        
        # Convert to response models
        po_responses = []
        for po in status_pos:
            items = [POItemResponse(**item) for item in po["items"]]
            po_response = POResponse(
                id=po["id"],
                po_number=po["po_number"],
                client_name=po["client_name"],
                status_macro=po["status_macro"],
                items=items,
                total_value=po["total_value"],
                margin_global=po["margin_global"],
                margin_percentage=po["margin_percentage"],
                created_at=po["created_at"],
                updated_at=po["updated_at"],
                created_by=po["created_by"]
            )
            po_responses.append(po_response)
        
        column = KanbanColumn(
            status=status_name,
            count=len(po_responses),
            pos=po_responses
        )
        columns.append(column)
    
    return KanbanBoardResponse(
        columns=columns,
        total_pos=len(mock_pos),
        tenant_id=current_user.tenant_id
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
    
    # Get mock data
    mock_pos = get_mock_pos(current_user.tenant_id)
    
    # Apply filters
    filtered_pos = mock_pos
    
    if status:
        filtered_pos = [po for po in filtered_pos if po["status_macro"] == status]
    
    if client_name:
        filtered_pos = [
            po for po in filtered_pos 
            if client_name.lower() in po["client_name"].lower()
        ]
    
    if po_number:
        filtered_pos = [
            po for po in filtered_pos 
            if po_number.lower() in po["po_number"].lower()
        ]
    
    # Apply pagination
    paginated_pos = filtered_pos[skip:skip + limit]
    
    # Convert to response models
    po_responses = []
    for po in paginated_pos:
        items = [POItemResponse(**item) for item in po["items"]]
        po_response = POResponse(
            id=po["id"],
            po_number=po["po_number"],
            client_name=po["client_name"],
            status_macro=po["status_macro"],
            items=items,
            total_value=po["total_value"],
            margin_global=po["margin_global"],
            margin_percentage=po["margin_percentage"],
            created_at=po["created_at"],
            updated_at=po["updated_at"],
            created_by=po["created_by"]
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
    
    # Get mock data
    mock_pos = get_mock_pos(current_user.tenant_id)
    
    # Find PO
    po = next((p for p in mock_pos if p["id"] == po_id), None)
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase Order {po_id} not found"
        )
    
    # Convert to response model
    items = [POItemResponse(**item) for item in po["items"]]
    return POResponse(
        id=po["id"],
        po_number=po["po_number"],
        client_name=po["client_name"],
        status_macro=po["status_macro"],
        items=items,
        total_value=po["total_value"],
        margin_global=po["margin_global"],
        margin_percentage=po["margin_percentage"],
        created_at=po["created_at"],
        updated_at=po["updated_at"],
        created_by=po["created_by"]
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
    
    **Parameters:**
    - **po_id**: Purchase Order ID
    - **to_status**: Target status
    - **reason**: Optional reason for the transition
    - **metadata**: Optional additional data
    
    **Returns:**
    - Result of the status transition
    """
    
    # Get mock data
    mock_pos = get_mock_pos(current_user.tenant_id)
    
    # Find PO
    po = next((p for p in mock_pos if p["id"] == request.po_id), None)
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase Order {request.po_id} not found"
        )
    
    from_status = po["status_macro"]
    
    # In production, use WorkflowService:
    # from backend.services.workflow_service import WorkflowService
    # workflow_service = WorkflowService(db)
    # result = workflow_service.transition_state(
    #     po_id=request.po_id,
    #     to_status=request.to_status,
    #     user_id=current_user.id,
    #     reason=request.reason,
    #     metadata=request.metadata
    # )
    
    # For demo, simulate validation
    valid_transitions = {
        "COMERCIAL": ["PCP"],
        "PCP": ["PRODUCAO", "COMERCIAL"],
        "PRODUCAO": ["EXPEDICAO_PENDENTE", "FATURAMENTO_PENDENTE"],
        "EXPEDICAO_PENDENTE": ["DESPACHO"],
        "FATURAMENTO_PENDENTE": ["DESPACHO"],
        "DESPACHO": ["CONCLUIDO"],
        "CONCLUIDO": []
    }
    
    # Check if transition is valid
    if request.to_status not in valid_transitions.get(from_status, []):
        return MoveStatusResponse(
            success=False,
            message=f"Invalid transition from {from_status} to {request.to_status}",
            po_id=request.po_id,
            from_status=from_status,
            to_status=request.to_status,
            validation_errors=[
                f"Cannot transition from {from_status} to {request.to_status}",
                f"Valid transitions from {from_status}: {', '.join(valid_transitions.get(from_status, []))}"
            ]
        )
    
    # Simulate successful transition
    po["status_macro"] = request.to_status
    po["updated_at"] = datetime.utcnow()
    
    return MoveStatusResponse(
        success=True,
        message=f"Successfully moved PO {po['po_number']} from {from_status} to {request.to_status}",
        po_id=request.po_id,
        from_status=from_status,
        to_status=request.to_status,
        validation_errors=None
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
    
    # Get mock data
    mock_pos = get_mock_pos(current_user.tenant_id)
    
    # Flatten items from all POs
    all_items = []
    for po in mock_pos:
        for item in po["items"]:
            item_with_po = {
                **item,
                "po_id": po["id"],
                "po_number": po["po_number"],
                "client_name": po["client_name"],
                "po_status": po["status_macro"]
            }
            all_items.append(item_with_po)
    
    # Apply filters
    filtered_items = all_items
    
    if status:
        filtered_items = [item for item in filtered_items if item["status_item"] == status]
    
    if sku:
        filtered_items = [
            item for item in filtered_items 
            if sku.lower() in item["sku"].lower()
        ]
    
    # Apply pagination
    paginated_items = filtered_items[skip:skip + limit]
    
    return {
        "items": paginated_items,
        "total": len(filtered_items),
        "skip": skip,
        "limit": limit
    }
