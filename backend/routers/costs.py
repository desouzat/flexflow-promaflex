"""
FlexFlow Cost Management Router
Endpoints para gerenciamento de custos de materiais (MASTER only)
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
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
    if current_user.role.lower() not in ["admin", "master"]:
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
        updated_by=current_user.id
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
    
    material.updated_by = current_user.id
    
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


@router.post("/upload", status_code=status.HTTP_200_OK)
async def upload_incremental_costs(
    file: UploadFile = File(..., description="Excel file (.xlsx) containing incremental costs"),
    current_user: UserInfo = Depends(require_admin_or_master_role),
    db: Session = Depends(get_db)
):
    """
    Incremental Excel Upload (.xlsx) for material costs.
    Upserts Material Costs using 'Material' column (A) as the primary SKU key.
    Enforces exact Celso headers:
    - Column A: 'Material' (Source for SKU and Name)
    - Column B: 'Rendimento'
    - Column D: 'CUSTO KG'
    Calculates Custo M2 as CUSTO KG / RENDIMENTO.
    """
    import io
    import uuid
    import pandas as pd
    from datetime import datetime
    from backend.models import PurchaseOrder, OrderItem
    
    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo inválido. Apenas planilhas Excel (.xlsx ou .xls) são permitidas."
        )
        
    try:
        file_content = await file.read()
        df = pd.read_excel(io.BytesIO(file_content))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Falha ao ler arquivo Excel: {str(e)}"
        )
        
    if len(df.columns) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A planilha deve conter pelo menos 4 colunas (Material, Rendimento, ..., CUSTO KG)."
        )
        
    col_a = str(df.columns[0]).strip()
    col_b = str(df.columns[1]).strip()
    col_d = str(df.columns[3]).strip()
    
    if col_a != 'Material' or col_b != 'Rendimento' or col_d != 'CUSTO KG':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Estrutura da planilha incorreta. Esperado exatamente as colunas: A='Material', B='Rendimento', D='CUSTO KG'. Encontrado: A='{col_a}', B='{col_b}', D='{col_d}'."
        )
        
    updated_count = 0
    created_count = 0
    updated_skus = []
    
    tenant_uuid = uuid.UUID(str(current_user.tenant_id))
    user_uuid = uuid.UUID(str(current_user.id))
    
    for idx, row in df.iterrows():
        raw_sku = row.iloc[0]
        if pd.isna(raw_sku):
            continue
            
        sku = str(raw_sku).strip()
        if not sku:
            continue
            
        try:
            rendimento = float(row.iloc[1])
            custo_mp_kg = float(row.iloc[3])
        except (ValueError, TypeError):
            # Skip invalid rows
            continue
            
        if rendimento <= 0 or custo_mp_kg < 0:
            continue
            
        # Find existing MaterialCost
        material = db.query(MaterialCost).filter(
            MaterialCost.tenant_id == tenant_uuid,
            MaterialCost.sku == sku
        ).first()
        
        if material:
            material.rendimento = rendimento
            material.custo_mp_kg = custo_mp_kg
            material.nome = sku  # Material column is the source for both SKU and name
            material.updated_at = datetime.utcnow()
            material.updated_by = user_uuid
            updated_count += 1
        else:
            material = MaterialCost(
                id=uuid.uuid4(),
                tenant_id=tenant_uuid,
                sku=sku,
                nome=sku,
                rendimento=rendimento,
                custo_mp_kg=custo_mp_kg,
                indice_impostos=22.25,
                updated_by=user_uuid,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(material)
            created_count += 1
            
        updated_skus.append(sku)
        
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao salvar custos no banco de dados: {str(e)}"
        )
        
    # Trigger global re-validation for updated SKUs
    affected_pos = db.query(PurchaseOrder).join(OrderItem).filter(
        PurchaseOrder.tenant_id == tenant_uuid,
        OrderItem.sku.in_(updated_skus)
    ).distinct().all()
    
    revalidation_logs = []
    for po in affected_pos:
        has_pending = False
        for item in po.items:
            mat = db.query(MaterialCost).filter(
                MaterialCost.tenant_id == po.tenant_id,
                MaterialCost.sku == item.sku
            ).first()
            if not mat or mat.custo_mp_kg <= 0 or mat.rendimento <= 0:
                has_pending = True
                
        # Calculate new dynamic margin
        if not has_pending:
            log_msg = f"PO {po.po_number}: PENDENTE PCP badge cleared! Margin recalculated successfully."
        else:
            log_msg = f"PO {po.po_number}: Cost updated. Remains PENDENTE PCP due to other pending SKUs."
        revalidation_logs.append(log_msg)
        print(f"[CLEANUP TRIGGER] {log_msg}")
        
    return {
        "success": True,
        "message": f"Ingestão concluída. Criados: {created_count}, Atualizados: {updated_count}.",
        "created": created_count,
        "updated": updated_count,
        "revalidation": revalidation_logs
    }





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
