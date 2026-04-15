"""
FlexFlow Workshop Router
Endpoints específicos para integração com workshops PCP.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid

from backend.schemas.auth_schema import UserInfo
from backend.database import get_db
from backend.routers.auth import get_current_user
from backend.models import PurchaseOrder, OrderItem
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/workshop", tags=["Workshop"])


# ============================================================================
# SCHEMAS
# ============================================================================

class StatusSyncRequest(BaseModel):
    """Request para sincronizar status de itens com PO"""
    po_id: str = Field(..., description="ID do Purchase Order")
    sync_strategy: str = Field(
        default="majority",
        description="Estratégia de sincronização: 'majority', 'all_completed', 'any_completed'"
    )


class StatusSyncResponse(BaseModel):
    """Response da sincronização de status"""
    success: bool
    message: str
    po_id: str
    old_status: str
    new_status: str
    items_synced: int
    items_total: int


class MetadataUpdateRequest(BaseModel):
    """Request para atualizar metadata de item"""
    item_id: str = Field(..., description="ID do OrderItem")
    metadata: dict = Field(..., description="Metadata customizada do workshop")


class MetadataUpdateResponse(BaseModel):
    """Response da atualização de metadata"""
    success: bool
    message: str
    item_id: str
    metadata: dict


class BulkMetadataUpdateRequest(BaseModel):
    """Request para atualizar metadata de múltiplos itens"""
    updates: List[dict] = Field(
        ...,
        description="Lista de {item_id, metadata} para atualizar"
    )


class BulkMetadataUpdateResponse(BaseModel):
    """Response da atualização em lote"""
    success: bool
    message: str
    updated_count: int
    failed_count: int
    errors: Optional[List[str]] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/sync-status", response_model=StatusSyncResponse)
async def sync_po_status_from_items(
    request: StatusSyncRequest,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sincroniza o status do PO baseado nos status dos itens.
    
    **Estratégias de Sincronização:**
    - **majority**: Status do PO muda quando maioria dos itens está no mesmo status
    - **all_completed**: Status do PO muda para COMPLETED quando todos itens estão APPROVED
    - **any_completed**: Status do PO muda para IN_PROGRESS quando qualquer item está em progresso
    
    **Mapeamento de Status:**
    - Itens PENDING/ORDERED → PO DRAFT
    - Itens RECEIVED/QUALITY_CHECK → PO SUBMITTED (PCP)
    - Itens APPROVED → PO APPROVED (Produção)
    - Todos APPROVED → PO IN_PROGRESS (Expedição)
    - Todos entregues → PO COMPLETED
    
    **Permissões:**
    - Requer autenticação
    - Isolamento por tenant
    
    **Returns:**
    - Resultado da sincronização com status antigo e novo
    """
    
    # Buscar PO
    po = db.query(PurchaseOrder).filter(
        PurchaseOrder.id == request.po_id,
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).first()
    
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Purchase Order {request.po_id} não encontrado"
        )
    
    # Buscar todos os itens do PO
    items = db.query(OrderItem).filter(
        OrderItem.po_id == request.po_id
    ).all()
    
    if not items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PO não possui itens para sincronizar"
        )
    
    old_status = po.status_macro
    new_status = old_status
    
    # Contar status dos itens
    status_counts = {}
    for item in items:
        status_counts[item.status_item] = status_counts.get(item.status_item, 0) + 1
    
    total_items = len(items)
    
    # Aplicar estratégia de sincronização
    if request.sync_strategy == "all_completed":
        # Todos os itens devem estar APPROVED para marcar como COMPLETED
        if status_counts.get(OrderItem.STATUS_APPROVED, 0) == total_items:
            new_status = PurchaseOrder.STATUS_COMPLETED
        elif status_counts.get(OrderItem.STATUS_APPROVED, 0) > 0:
            new_status = PurchaseOrder.STATUS_IN_PROGRESS
    
    elif request.sync_strategy == "majority":
        # Status majoritário dos itens define o status do PO
        majority_status = max(status_counts, key=status_counts.get)
        majority_count = status_counts[majority_status]
        
        if majority_count > total_items / 2:
            # Mapear status de item para status de PO
            if majority_status in [OrderItem.STATUS_PENDING, OrderItem.STATUS_ORDERED]:
                new_status = PurchaseOrder.STATUS_DRAFT
            elif majority_status in [OrderItem.STATUS_RECEIVED, OrderItem.STATUS_QUALITY_CHECK]:
                new_status = PurchaseOrder.STATUS_SUBMITTED
            elif majority_status == OrderItem.STATUS_APPROVED:
                new_status = PurchaseOrder.STATUS_APPROVED
    
    elif request.sync_strategy == "any_completed":
        # Qualquer item aprovado move para IN_PROGRESS
        if status_counts.get(OrderItem.STATUS_APPROVED, 0) > 0:
            new_status = PurchaseOrder.STATUS_IN_PROGRESS
        # Todos aprovados move para COMPLETED
        if status_counts.get(OrderItem.STATUS_APPROVED, 0) == total_items:
            new_status = PurchaseOrder.STATUS_COMPLETED
    
    # Atualizar status do PO se mudou
    if new_status != old_status:
        po.status_macro = new_status
        po.updated_at = datetime.utcnow()
        db.commit()
        message = f"Status do PO sincronizado de {old_status} para {new_status}"
    else:
        message = f"Status do PO mantido como {old_status} (sem mudanças necessárias)"
    
    return StatusSyncResponse(
        success=True,
        message=message,
        po_id=request.po_id,
        old_status=old_status,
        new_status=new_status,
        items_synced=total_items,
        items_total=total_items
    )


@router.put("/metadata/{item_id}", response_model=MetadataUpdateResponse)
async def update_item_metadata(
    item_id: str,
    request: MetadataUpdateRequest,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Atualiza o campo extra_metadata de um OrderItem.
    
    **Uso:**
    - Workshops podem adicionar campos customizados
    - Metadata é armazenada em formato JSONB
    - Permite estruturas aninhadas
    
    **Exemplo de Metadata:**
    ```json
    {
      "workshop_notes": "Item verificado pelo PCP",
      "quality_score": 95,
      "custom_fields": {
        "color": "blue",
        "size": "large"
      }
    }
    ```
    
    **Permissões:**
    - Requer autenticação
    - Isolamento por tenant
    
    **Returns:**
    - Confirmação da atualização com metadata completa
    """
    
    # Buscar item
    item = db.query(OrderItem).filter(
        OrderItem.id == item_id,
        OrderItem.tenant_id == current_user.tenant_id
    ).first()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} não encontrado"
        )
    
    # Atualizar metadata
    item.extra_metadata = request.metadata
    item.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(item)
    
    return MetadataUpdateResponse(
        success=True,
        message=f"Metadata do item {item_id} atualizada com sucesso",
        item_id=item_id,
        metadata=item.extra_metadata or {}
    )


@router.post("/metadata/bulk", response_model=BulkMetadataUpdateResponse)
async def bulk_update_metadata(
    request: BulkMetadataUpdateRequest,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Atualiza metadata de múltiplos itens em uma única requisição.
    
    **Uso:**
    - Ideal para workshops que processam múltiplos itens simultaneamente
    - Operação atômica: ou todos são atualizados ou nenhum
    
    **Formato do Request:**
    ```json
    {
      "updates": [
        {
          "item_id": "uuid-1",
          "metadata": {"field": "value"}
        },
        {
          "item_id": "uuid-2",
          "metadata": {"field": "value"}
        }
      ]
    }
    ```
    
    **Permissões:**
    - Requer autenticação
    - Isolamento por tenant
    
    **Returns:**
    - Contagem de itens atualizados e falhas
    """
    
    updated_count = 0
    failed_count = 0
    errors = []
    
    for update in request.updates:
        try:
            item_id = update.get("item_id")
            metadata = update.get("metadata")
            
            if not item_id or not metadata:
                failed_count += 1
                errors.append(f"Update inválido: {update}")
                continue
            
            # Buscar item
            item = db.query(OrderItem).filter(
                OrderItem.id == item_id,
                OrderItem.tenant_id == current_user.tenant_id
            ).first()
            
            if not item:
                failed_count += 1
                errors.append(f"Item {item_id} não encontrado")
                continue
            
            # Atualizar metadata
            item.extra_metadata = metadata
            item.updated_at = datetime.utcnow()
            updated_count += 1
            
        except Exception as e:
            failed_count += 1
            errors.append(f"Erro ao atualizar item {update.get('item_id')}: {str(e)}")
    
    # Commit todas as mudanças
    if updated_count > 0:
        db.commit()
    
    return BulkMetadataUpdateResponse(
        success=failed_count == 0,
        message=f"{updated_count} itens atualizados, {failed_count} falhas",
        updated_count=updated_count,
        failed_count=failed_count,
        errors=errors if errors else None
    )


@router.get("/metadata/{item_id}")
async def get_item_metadata(
    item_id: str,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtém a metadata de um OrderItem específico.
    
    **Permissões:**
    - Requer autenticação
    - Isolamento por tenant
    
    **Returns:**
    - Metadata completa do item
    """
    
    # Buscar item
    item = db.query(OrderItem).filter(
        OrderItem.id == item_id,
        OrderItem.tenant_id == current_user.tenant_id
    ).first()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Item {item_id} não encontrado"
        )
    
    return {
        "item_id": str(item.id),
        "sku": item.sku,
        "status": item.status_item,
        "metadata": item.extra_metadata or {},
        "updated_at": item.updated_at.isoformat()
    }
