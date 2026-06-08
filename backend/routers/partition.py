"""
FlexFlow Partition Router
API endpoints for PO partition workflow between PCP and Commercial.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field, validator
import uuid

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend.schemas.auth_schema import UserInfo
from backend.services.partition_service import PartitionService, PartitionError
from backend.models import PurchaseOrder, OrderItem

router = APIRouter(prefix="/api/partition", tags=["Partition"])


# ============================================================================
# SCHEMAS
# ============================================================================

class SuggestPartitionRequest(BaseModel):
    """Request to suggest a partition (PCP role)"""
    po_id: str = Field(..., description="Purchase Order ID")
    reason: str = Field(..., min_length=10, description="Technical reason for partition (min 10 chars)")
    
    @validator('reason')
    def validate_reason(cls, v):
        if not v or len(v.strip()) < 10:
            raise ValueError('Motivo deve ter no mínimo 10 caracteres')
        return v.strip()


class ExecutePartitionRequest(BaseModel):
    """Request to execute a partition (Commercial role)"""
    po_id: str = Field(..., description="Purchase Order ID")
    items_ship_now: List[str] = Field(..., description="List of item IDs to ship now")
    freight_strategy: str = Field(..., description="Freight strategy: PROPORTIONAL, FULL_ON_FIRST, or MANUAL")
    freight_ship_now: Optional[Decimal] = Field(None, description="Manual freight for ship now")
    freight_ship_later: Optional[Decimal] = Field(None, description="Manual freight for ship later")
    
    @validator('freight_strategy')
    def validate_strategy(cls, v):
        valid = ['PROPORTIONAL', 'FULL_ON_FIRST', 'MANUAL']
        if v not in valid:
            raise ValueError(f'Estratégia deve ser uma de: {", ".join(valid)}')
        return v
    
    @validator('freight_ship_now', 'freight_ship_later')
    def validate_freight(cls, v, values):
        if values.get('freight_strategy') == 'MANUAL' and v is None:
            raise ValueError('Estratégia MANUAL requer valores de frete')
        if v is not None and v < 0:
            raise ValueError('Valor de frete não pode ser negativo')
        return v


class PartitionItemResponse(BaseModel):
    """Item information for partition UI"""
    id: str
    sku: str
    quantity: int
    price: Decimal
    total_value: Decimal
    status_item: str
    partition_group: Optional[str] = None
    
    class Config:
        from_attributes = True


class PartitionPOResponse(BaseModel):
    """PO information for partition response"""
    id: str
    po_number: str
    status_macro: str
    items: List[PartitionItemResponse]
    shipping_cost: Decimal
    partition_reason: Optional[str] = None
    is_partitioned: bool
    
    class Config:
        from_attributes = True


class PartitionHistoryResponse(BaseModel):
    """Partition history for a PO"""
    po_id: str
    po_number: str
    is_partitioned: bool
    partition_reason: Optional[str]
    partition_metadata: Optional[dict]
    parent_po: Optional[dict]
    child_pos: List[dict]


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/suggest", status_code=status.HTTP_200_OK)
async def suggest_partition(
    request: SuggestPartitionRequest,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    PCP suggests a partition for a Purchase Order.
    
    **Role Required:** PCP
    
    **Process:**
    1. PCP identifies items that cannot be shipped together
    2. Provides technical reason for partition
    3. PO moves to WAITING_COMMERCIAL_PARTITION status
    4. Commercial team receives notification to execute partition
    
    **Returns:**
    - Updated PO with partition suggestion
    """
    
    # Validate user role
    if current_user.role.lower() not in ["pcp", "master", "leader", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas usuários PCP, LEADER, MASTER ou ADMIN podem sugerir partições"
        )
    
    try:
        service = PartitionService(db)
        po = service.suggest_partition(
            po_id=uuid.UUID(request.po_id),
            reason=request.reason,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id
        )
        
        return {
            "success": True,
            "message": f"Partição sugerida para o pedido {po.po_number}",
            "po_id": str(po.id),
            "po_number": po.po_number,
            "status": po.status_macro,
            "partition_reason": po.partition_reason
        }
        
    except PartitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": e.error_code, "message": e.message}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao sugerir partição: {str(e)}"
        )


@router.post("/execute", status_code=status.HTTP_200_OK)
async def execute_partition(
    request: ExecutePartitionRequest,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Commercial executes a partition on a Purchase Order.
    
    **Role Required:** COMERCIAL, MASTER, or LEADER
    
    **Process:**
    1. Commercial selects which items ship now vs later
    2. Chooses freight distribution strategy
    3. System creates Mother PO (ship now) and Child PO (ship later)
    4. Both POs return to SUBMITTED status for approval
    5. Full margin and present value recalculation
    
    **Freight Strategies:**
    - **PROPORTIONAL**: Freight split proportionally by item value
    - **FULL_ON_FIRST**: All freight on first shipment
    - **MANUAL**: Manually specify freight for each shipment
    
    **Returns:**
    - Mother PO and Child PO details
    """
    
    # Validate user role
    if current_user.role.lower() not in ["comercial", "master", "leader", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas usuários COMERCIAL, LEADER, MASTER ou ADMIN podem executar partições"
        )
    
    try:
        service = PartitionService(db)
        
        # Convert item IDs to UUID
        items_ship_now = [uuid.UUID(item_id) for item_id in request.items_ship_now]
        
        mother_po, child_po = service.execute_partition(
            po_id=uuid.UUID(request.po_id),
            items_ship_now=items_ship_now,
            freight_strategy=request.freight_strategy,
            user_id=current_user.id,
            tenant_id=current_user.tenant_id,
            freight_ship_now=request.freight_ship_now,
            freight_ship_later=request.freight_ship_later
        )
        
        return {
            "success": True,
            "message": "Partição executada com sucesso",
            "mother_po": {
                "id": str(mother_po.id),
                "po_number": mother_po.po_number,
                "status": mother_po.status_macro,
                "items_count": len(mother_po.items),
                "shipping_cost": float(mother_po.shipping_cost)
            },
            "child_po": {
                "id": str(child_po.id),
                "po_number": child_po.po_number,
                "status": child_po.status_macro,
                "items_count": len(child_po.items),
                "shipping_cost": float(child_po.shipping_cost)
            }
        }
        
    except PartitionError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": e.error_code, "message": e.message}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao executar partição: {str(e)}"
        )


@router.get("/pending", status_code=status.HTTP_200_OK)
async def get_pending_partitions(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all POs waiting for partition execution.
    
    **Role Required:** COMERCIAL, MASTER, or LEADER
    
    **Returns:**
    - List of POs in WAITING_COMMERCIAL_PARTITION status
    """
    
    # Validate user role
    if current_user.role.lower() not in ["comercial", "master", "leader", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas usuários COMERCIAL, LEADER, MASTER ou ADMIN podem visualizar partições pendentes"
        )
    
    try:
        pos = db.query(PurchaseOrder).filter(
            PurchaseOrder.tenant_id == current_user.tenant_id,
            PurchaseOrder.status_macro == PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION
        ).all()
        
        result = []
        for po in pos:
            items = []
            total_value = Decimal('0.00')
            
            for item in po.items:
                item_total = Decimal(str(item.price)) * item.quantity
                total_value += item_total
                
                items.append({
                    "id": str(item.id),
                    "sku": item.sku,
                    "quantity": item.quantity,
                    "price": float(item.price),
                    "total_value": float(item_total),
                    "status_item": item.status_item
                })
            
            result.append({
                "id": str(po.id),
                "po_number": po.po_number,
                "status": po.status_macro,
                "partition_reason": po.partition_reason,
                "items": items,
                "items_count": len(items),
                "total_value": float(total_value),
                "shipping_cost": float(po.shipping_cost or 0),
                "created_at": po.created_at.isoformat(),
                "updated_at": po.updated_at.isoformat()
            })
        
        return {
            "success": True,
            "count": len(result),
            "pending_partitions": result
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar partições pendentes: {str(e)}"
        )


@router.get("/history/{po_id}", response_model=PartitionHistoryResponse)
async def get_partition_history(
    po_id: str,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get complete partition history for a PO.
    
    Shows:
    - If PO has been partitioned
    - Parent PO (if this is a child)
    - Child POs (if this is a mother)
    - Partition metadata and traceability
    
    **Returns:**
    - Complete partition relationship tree
    """
    
    try:
        service = PartitionService(db)
        history = service.get_partition_history(
            po_id=uuid.UUID(po_id),
            tenant_id=current_user.tenant_id
        )
        
        if not history:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pedido {po_id} não encontrado"
            )
        
        return history
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar histórico de partição: {str(e)}"
        )


@router.get("/preview/{po_id}", status_code=status.HTTP_200_OK)
async def preview_partition(
    po_id: str,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Preview partition details for a PO.
    
    Provides all information needed for Commercial to execute partition:
    - All items with values
    - Current shipping cost
    - Partition reason from PCP
    
    **Returns:**
    - PO details ready for partition execution
    """
    
    try:
        po = db.query(PurchaseOrder).filter(
            PurchaseOrder.id == uuid.UUID(po_id),
            PurchaseOrder.tenant_id == current_user.tenant_id
        ).first()
        
        if not po:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pedido {po_id} não encontrado"
            )
        
        if po.status_macro != PurchaseOrder.STATUS_WAITING_COMMERCIAL_PARTITION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Pedido não está aguardando partição. Status atual: {po.status_macro}"
            )
        
        items = []
        total_value = Decimal('0.00')
        
        for item in po.items:
            item_total = Decimal(str(item.price)) * item.quantity
            total_value += item_total
            
            items.append({
                "id": str(item.id),
                "sku": item.sku,
                "quantity": item.quantity,
                "price": float(item.price),
                "total_value": float(item_total),
                "status_item": item.status_item,
                "is_personalized": item.is_personalized,
                "customization_notes": item.customization_notes
            })
        
        return {
            "success": True,
            "po": {
                "id": str(po.id),
                "po_number": po.po_number,
                "status": po.status_macro,
                "partition_reason": po.partition_reason,
                "items": items,
                "items_count": len(items),
                "total_value": float(total_value),
                "shipping_cost": float(po.shipping_cost or 0),
                "created_at": po.created_at.isoformat(),
                "updated_at": po.updated_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao visualizar partição: {str(e)}"
        )
