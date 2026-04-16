"""
FlexFlow Cost Management Router
Endpoints para gerenciamento de custos de materiais (MASTER only)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal

from backend.schemas.cost_schema import (
    MaterialCostCreate,
    MaterialCostUpdate,
    MaterialCostResponse,
    MaterialCostListResponse,
    GlobalSettingsResponse,
    GlobalSettingsUpdate
)
from backend.schemas.auth_schema import UserInfo
from backend.database import get_db
from backend.routers.auth import get_current_user
from backend.models import MaterialCost, User

router = APIRouter(prefix="/api/costs", tags=["Custos"])


def require_admin_or_master_role(current_user: UserInfo = Depends(get_current_user)):
    """
    Dependency para verificar se o usuário tem role admin ou master.
    Apenas usuários admin ou master podem acessar endpoints de custos.
    """
    if current_user.role not in ["admin", "master"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Apenas usuários admin ou master podem gerenciar custos."
        )
    return current_user


@router.get("/materials", response_model=MaterialCostListResponse)
async def list_material_costs(
    skip: int = Query(0, ge=0, description="Número de registros a pular"),
    limit: int = Query(100, ge=1, le=1000, description="Máximo de registros a retornar"),
    sku: Optional[str] = Query(None, description="Filtrar por SKU (busca parcial)"),
    current_user: UserInfo = Depends(require_admin_or_master_role),
    db: Session = Depends(get_db)
):
    """
    Listar todos os custos de materiais.
    
    **Acesso:** Admin ou Master
    
    **Query Parameters:**
    - **skip**: Paginação - registros a pular
    - **limit**: Paginação - máximo de registros
    - **sku**: Filtro opcional por SKU
    
    **Returns:**
    - Lista de custos de materiais
    """
    
    # Query base
    query = db.query(MaterialCost).filter(
        MaterialCost.tenant_id == current_user.tenant_id
    )
    
    # Aplicar filtro de SKU se fornecido
    if sku:
        query = query.filter(MaterialCost.sku.ilike(f"%{sku}%"))
    
    # Contar total
    total = query.count()
    
    # Aplicar paginação
    materials = query.order_by(MaterialCost.sku).offset(skip).limit(limit).all()
    
    # Converter para response
    items = [
        MaterialCostResponse(
            id=str(material.id),
            tenant_id=str(material.tenant_id),
            sku=material.sku,
            nome=material.nome,
            custo_mp_kg=Decimal(str(material.custo_mp_kg)),
            rendimento=Decimal(str(material.rendimento)),
            indice_impostos=Decimal(str(material.indice_impostos)),
            created_at=material.created_at,
            updated_at=material.updated_at,
            updated_by=str(material.updated_by) if material.updated_by else None
        )
        for material in materials
    ]
    
    return MaterialCostListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/materials/{sku}", response_model=MaterialCostResponse)
async def get_material_cost(
    sku: str,
    current_user: UserInfo = Depends(require_admin_or_master_role),
    db: Session = Depends(get_db)
):
    """
    Obter custo de um material específico por SKU.
    
    **Acesso:** Admin ou Master
    
    **Parameters:**
    - **sku**: SKU do material
    
    **Returns:**
    - Dados de custo do material
    """
    
    material = db.query(MaterialCost).filter(
        MaterialCost.tenant_id == current_user.tenant_id,
        MaterialCost.sku == sku
    ).first()
    
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material com SKU '{sku}' não encontrado"
        )
    
    return MaterialCostResponse(
        id=str(material.id),
        tenant_id=str(material.tenant_id),
        sku=material.sku,
        nome=material.nome,
        custo_mp_kg=Decimal(str(material.custo_mp_kg)),
        rendimento=Decimal(str(material.rendimento)),
        indice_impostos=Decimal(str(material.indice_impostos)),
        created_at=material.created_at,
        updated_at=material.updated_at,
        updated_by=str(material.updated_by) if material.updated_by else None
    )


@router.post("/materials", response_model=MaterialCostResponse, status_code=status.HTTP_201_CREATED)
async def create_material_cost(
    material_data: MaterialCostCreate,
    current_user: UserInfo = Depends(require_admin_or_master_role),
    db: Session = Depends(get_db)
):
    """
    Criar novo custo de material.
    
    **Acesso:** Admin ou Master
    
    **Body:**
    - Dados do material (sku, nome, custo_mp_kg, rendimento, indice_impostos)
    
    **Returns:**
    - Material criado
    """
    
    # Verificar se SKU já existe
    existing = db.query(MaterialCost).filter(
        MaterialCost.tenant_id == current_user.tenant_id,
        MaterialCost.sku == material_data.sku
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Material com SKU '{material_data.sku}' já existe"
        )
    
    # Criar novo material
    material = MaterialCost(
        tenant_id=current_user.tenant_id,
        sku=material_data.sku,
        nome=material_data.nome,
        custo_mp_kg=material_data.custo_mp_kg,
        rendimento=material_data.rendimento,
        indice_impostos=material_data.indice_impostos,
        updated_by=current_user.user_id
    )
    
    db.add(material)
    db.commit()
    db.refresh(material)
    
    return MaterialCostResponse(
        id=str(material.id),
        tenant_id=str(material.tenant_id),
        sku=material.sku,
        nome=material.nome,
        custo_mp_kg=Decimal(str(material.custo_mp_kg)),
        rendimento=Decimal(str(material.rendimento)),
        indice_impostos=Decimal(str(material.indice_impostos)),
        created_at=material.created_at,
        updated_at=material.updated_at,
        updated_by=str(material.updated_by) if material.updated_by else None
    )


@router.put("/materials/{sku}", response_model=MaterialCostResponse)
async def update_material_cost(
    sku: str,
    material_data: MaterialCostUpdate,
    current_user: UserInfo = Depends(require_admin_or_master_role),
    db: Session = Depends(get_db)
):
    """
    Atualizar custo de material existente.
    
    **Acesso:** Admin ou Master
    
    **Parameters:**
    - **sku**: SKU do material
    
    **Body:**
    - Dados a atualizar (campos opcionais)
    
    **Returns:**
    - Material atualizado
    """
    
    material = db.query(MaterialCost).filter(
        MaterialCost.tenant_id == current_user.tenant_id,
        MaterialCost.sku == sku
    ).first()
    
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material com SKU '{sku}' não encontrado"
        )
    
    # Atualizar campos fornecidos
    update_data = material_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(material, field, value)
    
    material.updated_by = current_user.user_id
    
    db.commit()
    db.refresh(material)
    
    return MaterialCostResponse(
        id=str(material.id),
        tenant_id=str(material.tenant_id),
        sku=material.sku,
        nome=material.nome,
        custo_mp_kg=Decimal(str(material.custo_mp_kg)),
        rendimento=Decimal(str(material.rendimento)),
        indice_impostos=Decimal(str(material.indice_impostos)),
        created_at=material.created_at,
        updated_at=material.updated_at,
        updated_by=str(material.updated_by) if material.updated_by else None
    )


@router.delete("/materials/{sku}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material_cost(
    sku: str,
    current_user: UserInfo = Depends(require_admin_or_master_role),
    db: Session = Depends(get_db)
):
    """
    Deletar custo de material.
    
    **Acesso:** Admin ou Master
    
    **Parameters:**
    - **sku**: SKU do material
    
    **Returns:**
    - 204 No Content
    """
    
    material = db.query(MaterialCost).filter(
        MaterialCost.tenant_id == current_user.tenant_id,
        MaterialCost.sku == sku
    ).first()
    
    if not material:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material com SKU '{sku}' não encontrado"
        )
    
    db.delete(material)
    db.commit()
    
    return None


@router.get("/settings", response_model=GlobalSettingsResponse)
async def get_global_settings(
    current_user: UserInfo = Depends(require_admin_or_master_role),
    db: Session = Depends(get_db)
):
    """
    Obter configurações globais de custos.
    
    **Acesso:** Admin ou Master
    
    **Returns:**
    - Configurações globais (índice de impostos padrão)
    """
    
    # Por enquanto, retorna valor padrão
    # Futuramente pode ser armazenado em uma tabela de configurações
    return GlobalSettingsResponse(
        indice_impostos_padrao=Decimal("22.25"),
        tenant_id=str(current_user.tenant_id)
    )
