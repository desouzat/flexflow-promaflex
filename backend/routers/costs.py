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
                indice_impostos=9.25,  # FF-HARDENING-015: PIS/COFINS unified rate (was 22.25)
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


@router.post("/upload-onet", status_code=status.HTTP_200_OK)
async def upload_onet_costs(
    file: UploadFile = File(..., description="Excel ONET cost file (.xlsx) from FlowCare — Ewaldo format"),
    current_user: UserInfo = Depends(require_admin_or_master_role),
    db: Session = Depends(get_db)
):
    """
    FF-HARDENING-016 Bug 3: Ingest SKU cost data from Ewaldo's FlowCare ONET spreadsheet.

    Columns are detected by their header TEXT (case-insensitive substring match),
    not by fixed positional index. This makes the parser resilient to column reordering.

    Header keywords resolved:
    - "SKU Onet"          -> sku column
    - "cod estruturado"   -> nome (item description)
    - "Custo Total kg"    -> custo_total_kg (checked BEFORE bare 'custo' to avoid mis-match)
    - "CUSTO"             -> custo_mp_kg (unit raw material cost)
    - "RENDIMENTO"        -> rendimento (kg yield per unit)

    Tax rate is fixed at 9.25% (PIS/COFINS unified rate).
    Uses upsert logic: existing SKUs are updated; new SKUs are created.
    Rows with null/empty SKU values are strictly skipped.
    """
    import io
    import uuid
    import pandas as pd
    from datetime import datetime

    if not file.filename.lower().endswith(('.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo inválido. Apenas planilhas Excel (.xlsx ou .xls) são permitidas."
        )

    try:
        file_content = await file.read()
        # Read without a header so we can detect the real header row dynamically.
        raw_df = pd.read_excel(io.BytesIO(file_content), header=None)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Falha ao ler arquivo Excel: {str(e)}"
        )

    # ── Detect header row: first row that contains a cell with 'sku' ─────────────
    header_row_idx = None
    for row_idx, row in raw_df.iterrows():
        for cell in row:
            if isinstance(cell, str) and 'sku' in cell.lower():
                header_row_idx = row_idx
                break
        if header_row_idx is not None:
            break

    if header_row_idx is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Não foi possível localizar a linha de cabeçalho (uma linha contendo 'SKU'). "
                "Verifique se o arquivo é o formato ONET FlowCare (base_custo_produtos_sku_onet.xlsx)."
            )
        )

    # Re-read using the detected header row index
    try:
        df = pd.read_excel(io.BytesIO(file_content), header=header_row_idx)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Falha ao ler arquivo Excel com cabeçalho detectado: {str(e)}"
        )

    # ── Map column names by matching header text (case-insensitive) ───────────────
    # Normalise: strip whitespace, collapse multiple spaces, convert to lowercase.
    col_map = {}   # semantic role -> original DataFrame column name
    for col in df.columns:
        if not isinstance(col, str):
            continue
        norm = ' '.join(col.strip().lower().split())

        if 'sku' in norm and 'onet' in norm:
            col_map.setdefault('sku', col)
        elif 'cod estruturado' in norm:
            col_map.setdefault('nome', col)
        # 'custo total' MUST be matched before bare 'custo' to avoid mis-mapping
        elif 'custo total' in norm:
            col_map.setdefault('custo_total_kg', col)
        elif norm == 'custo' or ('custo' in norm and 'total' not in norm):
            col_map.setdefault('custo_mp_kg', col)
        elif 'rendimento' in norm:
            col_map.setdefault('rendimento', col)

    # Validate that the three required columns were found
    required = ['sku', 'custo_mp_kg', 'rendimento']
    missing_cols = [r for r in required if r not in col_map]
    if missing_cols:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Colunas obrigatórias não encontradas: {missing_cols}. "
                f"Colunas detectadas no arquivo: {list(df.columns)}. "
                "Verifique se o arquivo é o formato ONET FlowCare."
            )
        )

    tenant_uuid = uuid.UUID(str(current_user.tenant_id))
    user_uuid = uuid.UUID(str(current_user.id))

    updated_count = 0
    created_count = 0
    skipped_count = 0
    updated_skus = []
    errors = []

    # Skip the first data row (it repeats the header labels: "SKU Onet", "cod estruturado Onet", ...)
    data_df = df  # Use col_map-based access; label rows are skipped inside the loop

    for idx, row in data_df.iterrows():
        raw_sku = row.get(col_map['sku'])

        # Strictly skip rows with null/empty/NaN SKU
        if raw_sku is None or (isinstance(raw_sku, float) and pd.isna(raw_sku)):
            skipped_count += 1
            continue
        sku = str(raw_sku).strip()
        if not sku or sku.lower() in ('nan', 'none', ''):
            skipped_count += 1
            continue

        # Skip rows that repeat column header labels as data values
        if 'sku' in sku.lower():
            skipped_count += 1
            continue

        # nome: prefer the cod_estruturado column, fall back to the SKU itself
        nome_col = col_map.get('nome')
        raw_cod = row.get(nome_col) if nome_col else None
        nome = (
            str(raw_cod).strip()
            if raw_cod is not None and not (isinstance(raw_cod, float) and pd.isna(raw_cod))
            else sku
        )
        if 'cod estruturado' in nome.lower():
            skipped_count += 1
            continue

        raw_custo      = row.get(col_map['custo_mp_kg'])
        raw_rendimento = row.get(col_map['rendimento'])

        try:
            custo_mp_kg = float(raw_custo)
            rendimento = float(raw_rendimento)
        except (ValueError, TypeError):
            errors.append(f"SKU {sku}: valores inválidos em CUSTO ou RENDIMENTO — linha ignorada.")
            skipped_count += 1
            continue

        if rendimento <= 0 or custo_mp_kg < 0:
            errors.append(f"SKU {sku}: rendimento deve ser > 0 e custo >= 0 — linha ignorada.")
            skipped_count += 1
            continue

        material = db.query(MaterialCost).filter(
            MaterialCost.tenant_id == tenant_uuid,
            MaterialCost.sku == sku
        ).first()

        if material:
            material.nome = nome
            material.custo_mp_kg = custo_mp_kg
            material.rendimento = rendimento
            # Do NOT overwrite indice_impostos if already set — preserve admin customizations.
            # Only set if it is still the old default (22.25) — migrate it to 9.25.
            if float(material.indice_impostos) == 22.25:
                material.indice_impostos = 9.25  # FF-HARDENING-015: migrate legacy rate
            material.updated_at = datetime.utcnow()
            material.updated_by = user_uuid
            updated_count += 1
        else:
            material = MaterialCost(
                id=uuid.uuid4(),
                tenant_id=tenant_uuid,
                sku=sku,
                nome=nome,
                rendimento=rendimento,
                custo_mp_kg=custo_mp_kg,
                indice_impostos=9.25,  # FF-HARDENING-015: PIS/COFINS unified rate
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
            detail=f"Erro ao salvar custos ONET no banco de dados: {str(e)}"
        )

    print(
        f"[FF-HARDENING-016] ONET ingest (name-based cols): {created_count} criados, "
        f"{updated_count} atualizados, {skipped_count} ignorados. "
        f"Mapeamento: {col_map}. SKUs: {updated_skus[:10]}{'...' if len(updated_skus) > 10 else ''}",
        flush=True
    )

    return {
        "success": True,
        "message": (
            f"Ingestão ONET concluída. Criados: {created_count}, "
            f"Atualizados: {updated_count}, Ignorados: {skipped_count}."
        ),
        "created": created_count,
        "updated": updated_count,
        "skipped": skipped_count,
        "errors": errors[:20],
        "skus_processed": updated_skus[:50],
        "columns_detected": col_map   # diagnostic: shows which columns were matched
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
        indice_impostos_padrao=Decimal("9.25"),  # FF-HARDENING-015: PIS/COFINS unified rate (was 22.25)
        tenant_id=str(current_user.tenant_id)
    )
