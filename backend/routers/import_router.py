"""
FlexFlow Import Router
Endpoints for file upload and import configuration.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import uuid
from datetime import datetime, timezone

from backend.schemas.import_schema import (
    ImportMapping,
    ImportResponse,
    ImportRequest,
    ColumnMapping,
    ImportFieldType,
    ImportItemData,
    FinanceDecisionRequest,
    FinanceDecisionResponse,
    FinanceDecision,
    ConfirmStagingPayload,
    CancelStagingPayload,
    CancelStagingItemSchema,
)
from backend.schemas.auth_schema import UserInfo
from backend.services.import_service import ImportService
from backend.services.file_service import FileService
from backend.database import get_db
from backend.routers.auth import get_current_user
from backend.models import OrderItem, AuditLog, PurchaseOrder, StagingSession

router = APIRouter(prefix="/api/import", tags=["Import"])

import threading as _threading

# In-memory storage for import configurations (replace with database in production)
import_configs_storage = {}

# ── In-memory Heartbeat Lock ──────────────────────────────────────────────────
# Tracks operators who currently have the Mesa de Conferência open.
# Keyed by tenant_id (str) → {user_email, user_name, expires_at (datetime UTC)}
_heartbeat_lock = _threading.Lock()
_active_mesa_users: dict = {}


@router.post("/upload", response_model=ImportResponse)
async def upload_and_import_file(
    file: UploadFile = File(..., description="Excel or CSV file to import"),
    mapping_json: str = Form(..., description="JSON string of column mapping"),
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload and import a Purchase Order from Excel/CSV file.
    
    **Parameters:**
    - **file**: Excel (.xlsx, .xls) or CSV file containing PO data
    - **mapping_json**: JSON string with column mapping configuration
    
    **Returns:**
    - Import result with success status and details
    
    **Example mapping_json:**
    ```json
    {
        "mappings": [
            {"column_name": "PO Number", "field_type": "po_number"},
            {"column_name": "Client", "field_type": "client_name"},
            {"column_name": "SKU", "field_type": "sku"},
            {"column_name": "Qty", "field_type": "quantity"},
            {"column_name": "Price", "field_type": "price_unit"},
            {"column_name": "Cost MP", "field_type": "cost_mp"},
            {"column_name": "Cost MO", "field_type": "cost_mo"},
            {"column_name": "Cost Energy", "field_type": "cost_energy"},
            {"column_name": "Cost Gas", "field_type": "cost_gas"}
        ]
    }
    ```
    """
    
    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )
    
    allowed_extensions = ['.xlsx', '.xls', '.csv']
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
        )
    
    # Parse mapping JSON
    try:
        mapping_dict = json.loads(mapping_json)
        mapping = ImportMapping(**mapping_dict)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid mapping JSON: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid mapping configuration: {str(e)}"
        )
    
    # Read file content
    try:
        file_content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading file: {str(e)}"
        )
    
    # Create import request
    import_request = ImportRequest(
        file_content=file_content,
        file_name=file.filename,
        mapping=mapping,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id
    )
    
    # Execute import — parse only, no production DB write
    import_service = ImportService(db)
    response = import_service.import_po(import_request)

    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=response.message
        )

    # ── Upsert staging session so other operators can load this batch ──────────
    try:
        _upsert_staging_session(
            db=db,
            tenant_id=str(current_user.tenant_id),
            po_list=response.po_list or [],
            updated_by=getattr(current_user, 'email', str(current_user.id))
        )
    except Exception:
        pass  # Best-effort; never block the import response

    return response


@router.post("/headers")
async def get_file_headers(
    file: UploadFile = File(..., description="Excel or CSV file"),
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Extract column headers from uploaded file for mapping UI.
    
    This endpoint helps users create the column mapping by showing
    what columns are available in their file.
    
    **Parameters:**
    - **file**: Excel or CSV file
    
    **Returns:**
    - List of column names found in the file
    """
    
    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file provided"
        )
    
    # Read file content
    try:
        file_content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading file: {str(e)}"
        )
    
    # Extract headers
    try:
        import_service = ImportService(db)
        headers = import_service.get_file_headers(file_content, file.filename)
        
        return {
            "filename": file.filename,
            "headers": headers,
            "count": len(headers)
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/field-types")
def get_available_field_types(
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Get list of available field types for mapping.
    
    This helps the frontend build the mapping UI by showing
    which system fields are available.
    
    **Returns:**
    - List of field types with descriptions
    """
    
    field_types = [
        # Core required fields
        {
            "value": ImportFieldType.PO_NUMBER,
            "label": "Pedido (PO Number)",
            "description": "Purchase Order number",
            "required": True
        },
        {
            "value": ImportFieldType.CLIENT_NAME,
            "label": "Cliente (Client Name)",
            "description": "Customer/Client name",
            "required": True
        },
        {
            "value": ImportFieldType.SKU,
            "label": "SKU",
            "description": "Product SKU/Code",
            "required": True
        },
        {
            "value": ImportFieldType.QUANTITY,
            "label": "Qtd (Quantity)",
            "description": "Item quantity (must be positive integer)",
            "required": True
        },
        
        # Optional ONET fields
        {
            "value": ImportFieldType.DESCRIPTION,
            "label": "Descrição (Description)",
            "description": "Product description",
            "required": False
        },
        {
            "value": ImportFieldType.UNIT,
            "label": "Unidade (Unit)",
            "description": "Unit of measure (UN, KG, etc)",
            "required": False
        },
        {
            "value": ImportFieldType.WIDTH,
            "label": "Largura (Width)",
            "description": "Width in mm",
            "required": False
        },
        {
            "value": ImportFieldType.LENGTH,
            "label": "Comprimento (Length)",
            "description": "Length in mm",
            "required": False
        },
        {
            "value": ImportFieldType.LEAD_TIME,
            "label": "Lead Time",
            "description": "Production lead time in days",
            "required": False
        },
        {
            "value": ImportFieldType.DELIVERY_DATE,
            "label": "Data Entrega (Delivery Date)",
            "description": "Delivery date (DD/MM/YYYY)",
            "required": False
        },
        {
            "value": ImportFieldType.BILLING_DATE,
            "label": "Data Faturamento (Billing Date)",
            "description": "Billing date (DD/MM/YYYY)",
            "required": False
        },
        {
            "value": ImportFieldType.ICMS_PERCENT,
            "label": "% ICMS",
            "description": "ICMS tax percentage",
            "required": False
        },
        {
            "value": ImportFieldType.IPI,
            "label": "IPI",
            "description": "IPI tax value",
            "required": False
        },
        {
            "value": ImportFieldType.FREIGHT,
            "label": "Frete (Freight)",
            "description": "Freight/shipping cost",
            "required": False
        },
        {
            "value": ImportFieldType.PAYMENT_TERMS,
            "label": "Condição Pagamento (Payment Terms)",
            "description": "Payment terms/conditions",
            "required": False
        },
        {
            "value": ImportFieldType.BLOCK_STATUS,
            "label": "Bloqueio (Block Status)",
            "description": "Block/Hold status",
            "required": False
        },
        {
            "value": ImportFieldType.BALANCE,
            "label": "Saldo (Balance)",
            "description": "Balance amount",
            "required": False
        },
        {
            "value": ImportFieldType.DELAY,
            "label": "Atraso (Delay)",
            "description": "Delay in days",
            "required": False
        },
        {
            "value": ImportFieldType.SALESPERSON,
            "label": "Vendedor (Salesperson)",
            "description": "Salesperson name",
            "required": False
        },
        
        # Legacy cost fields (optional)
        {
            "value": ImportFieldType.PRICE_UNIT,
            "label": "Unit Price",
            "description": "Price per unit (must be non-negative)",
            "required": False
        },
        {
            "value": ImportFieldType.COST_MP,
            "label": "Material Cost",
            "description": "Cost of raw materials (Matéria Prima)",
            "required": False
        },
        {
            "value": ImportFieldType.COST_MO,
            "label": "Labor Cost",
            "description": "Cost of labor (Mão de Obra)",
            "required": False
        },
        {
            "value": ImportFieldType.COST_ENERGY,
            "label": "Energy Cost",
            "description": "Energy/electricity cost",
            "required": False
        },
        {
            "value": ImportFieldType.COST_GAS,
            "label": "Gas Cost",
            "description": "Gas cost",
            "required": False
        }
    ]
    
    return {
        "field_types": field_types,
        "total": len(field_types)
    }


@router.post("/configs")
def save_import_config(
    config_name: str,
    mapping: ImportMapping,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Save an import configuration for reuse.
    
    Users can save their column mappings with a name and reuse them
    for future imports with the same file structure.
    
    **Parameters:**
    - **config_name**: Name for this configuration
    - **mapping**: Column mapping configuration
    
    **Returns:**
    - Saved configuration details
    """
    
    # Create config key (tenant_id + config_name)
    config_key = f"{current_user.tenant_id}:{config_name}"
    
    # Check if config already exists
    if config_key in import_configs_storage:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Configuration '{config_name}' already exists"
        )
    
    # Save configuration
    config_data = {
        "name": config_name,
        "tenant_id": current_user.tenant_id,
        "created_by": current_user.id,
        "mapping": mapping.model_dump(),
        "created_at": "2026-03-17T00:00:00Z"  # Would use datetime.utcnow() in production
    }
    
    import_configs_storage[config_key] = config_data
    
    return {
        "message": f"Configuration '{config_name}' saved successfully",
        "config": config_data
    }


@router.get("/configs")
def list_import_configs(
    current_user: UserInfo = Depends(get_current_user)
):
    """
    List all saved import configurations for current tenant.
    
    **Returns:**
    - List of saved configurations
    """
    
    # Filter configs by tenant
    tenant_configs = [
        config for key, config in import_configs_storage.items()
        if key.startswith(f"{current_user.tenant_id}:")
    ]
    
    return {
        "configs": tenant_configs,
        "count": len(tenant_configs)
    }


@router.get("/configs/{config_name}")
def get_import_config(
    config_name: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Get a specific import configuration by name.
    
    **Parameters:**
    - **config_name**: Name of the configuration
    
    **Returns:**
    - Configuration details
    """
    
    config_key = f"{current_user.tenant_id}:{config_name}"
    
    if config_key not in import_configs_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration '{config_name}' not found"
        )
    
    return import_configs_storage[config_key]


@router.delete("/configs/{config_name}")
def delete_import_config(
    config_name: str,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Delete an import configuration.
    
    **Parameters:**
    - **config_name**: Name of the configuration to delete
    
    **Returns:**
    - Deletion confirmation
    """
    
    config_key = f"{current_user.tenant_id}:{config_name}"
    
    if config_key not in import_configs_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration '{config_name}' not found"
        )
    
    del import_configs_storage[config_key]
    
    return {
        "message": f"Configuration '{config_name}' deleted successfully"
    }


@router.post("/upload-attachment")
async def upload_attachment(
    file: UploadFile = File(..., description="Attachment file (PDF, JPG, PNG)"),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Upload an attachment file for a personalized order item.
    
    **Parameters:**
    - **file**: Attachment file (PDF, JPG, PNG) - Max 5MB
    
    **Returns:**
    - File path and original filename
    """
    
    from backend.services.gcs_service import GCSService
    gcs_service = GCSService()
    
    try:
        file_path, original_filename = await gcs_service.upload_file(
            file,
            str(current_user.tenant_id)
        )
        
        return {
            "success": True,
            "file_path": file_path,
            "original_filename": original_filename,
            "message": "File uploaded successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error uploading file: {str(e)}"
        )


@router.post("/validate-staging-item")
def validate_staging_item(
    is_personalized: bool = Form(...),
    is_new_client: bool = Form(...),
    customization_notes: Optional[str] = Form(None),
    attachment_path: Optional[str] = Form(None),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Validate a staging item against business rules.
    
    **Business Rules:**
    1. If is_personalized is True, customization_notes is MANDATORY
    2. If is_personalized is True AND is_new_client is True, attachment is MANDATORY
    
    **Returns:**
    - Validation result with errors if any
    """
    
    is_valid, error_msg = FileService.validate_customization_rules(
        is_personalized=is_personalized,
        is_new_client=is_new_client,
        customization_notes=customization_notes,
        attachment_path=attachment_path
    )
    
    return {
        "valid": is_valid,
        "errors": [error_msg] if error_msg else [],
        "is_personalized": is_personalized,
        "is_new_client": is_new_client
    }


from pydantic import BaseModel
from typing import List

class SyncS3Request(BaseModel):
    filenames: Optional[List[str]] = None
    file_keys: Optional[List[str]] = None


# ============================================================================
# HELPER: Staging Session Upsert
# ============================================================================

def _upsert_staging_session(db, tenant_id: str, po_list: list, updated_by: str) -> None:
    """
    Insert or replace the active StagingSession for a tenant.
    One session per tenant (enforced by unique index on tenant_id).
    """
    import uuid as _uuid
    from sqlalchemy import select as _select
    from datetime import datetime as _dt, timezone as _tz

    tenant_uuid = _uuid.UUID(str(tenant_id))
    existing = db.execute(
        _select(StagingSession).where(StagingSession.tenant_id == tenant_uuid)
    ).scalar_one_or_none()

    if existing:
        existing.data = po_list
        existing.updated_by = updated_by
        existing.updated_at = _dt.now(_tz.utc)
    else:
        session = StagingSession(
            id=_uuid.uuid4(),
            tenant_id=tenant_uuid,
            data=po_list,
            updated_by=updated_by,
            updated_at=_dt.now(_tz.utc)
        )
        db.add(session)
    db.commit()


# ============================================================================
# NEW ENDPOINT: GET /staging-session
# ============================================================================

@router.get("/staging-session")
def get_staging_session(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve the active Mesa de Conferência staging session for this tenant.
    Returns {po_list: [], updated_by: null, updated_at: null} if no session exists.
    """
    from sqlalchemy import select as _select
    import uuid as _uuid

    tenant_uuid = _uuid.UUID(str(current_user.tenant_id))
    session = db.execute(
        _select(StagingSession).where(StagingSession.tenant_id == tenant_uuid)
    ).scalar_one_or_none()

    if not session:
        return {"po_list": [], "updated_by": None, "updated_at": None}

    return {
        "po_list": session.data or [],
        "updated_by": session.updated_by,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None
    }


# ============================================================================
# NEW ENDPOINT: PUT /staging-session  (auto-save)
# ============================================================================

class StagingSessionUpdateRequest(BaseModel):
    po_list: list


@router.put("/staging-session")
def update_staging_session(
    payload: StagingSessionUpdateRequest,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Auto-save the current po_list state to the DB staging session.
    Called by the frontend whenever an operator edits a dropdown or checkbox.
    """
    try:
        _upsert_staging_session(
            db=db,
            tenant_id=str(current_user.tenant_id),
            po_list=payload.po_list,
            updated_by=getattr(current_user, 'email', str(current_user.id))
        )
        return {"success": True}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao salvar sessão de staging: {str(exc)}"
        ) from exc


# ============================================================================
# NEW ENDPOINT: DELETE /staging-session  (clear/discard session)
# ============================================================================

@router.delete("/staging-session")
def delete_staging_session(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Purge/clear the active Mesa de Conferência staging session for this tenant.
    Called when an operator cancels or discards the current staging session.
    """
    import uuid as _uuid
    try:
        tenant_id_val = current_user.tenant_id
        if isinstance(tenant_id_val, str):
            tenant_id_val = _uuid.UUID(tenant_id_val)

        db.query(StagingSession).filter(StagingSession.tenant_id == tenant_id_val).delete(synchronize_session=False)
        db.commit()
        return {"success": True, "message": "Sessão de staging descartada com sucesso."}
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao descartar sessão de staging: {str(exc)}"
        ) from exc


# ============================================================================
# HEARTBEAT ENDPOINTS — Concurrency Warning Banner
# ============================================================================

class HeartbeatRequest(BaseModel):
    user_name: str
    session_id: Optional[str] = None


@router.post("/mesa-heartbeat")
def post_mesa_heartbeat(
    payload: HeartbeatRequest,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Claim or refresh the heartbeat lock for the Mesa de Conferência.
    Must be called every 60 seconds by the active user's browser.
    Lock expires after 5 minutes of inactivity.
    """
    from datetime import datetime as _dt, timezone as _tz, timedelta as _td
    tenant_key = str(current_user.tenant_id)
    user_email = getattr(current_user, 'email', str(current_user.id))
    expires_at = _dt.now(_tz.utc) + _td(minutes=5)

    with _heartbeat_lock:
        _active_mesa_users[tenant_key] = {
            "user_email": user_email,
            "user_name": payload.user_name,
            "session_id": payload.session_id,
            "expires_at": expires_at
        }
    return {"success": True, "expires_at": expires_at.isoformat()}


@router.get("/mesa-lock-status")
def get_mesa_lock_status(
    session_id: Optional[str] = None,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Check if another operator has the Mesa open for this tenant.
    Returns {locked: false} if no active session or if the current user owns it.
    Returns {locked: true, holder_name, holder_email, since} if another session is active.
    """
    from datetime import datetime as _dt, timezone as _tz
    tenant_key = str(current_user.tenant_id)
    caller_email = getattr(current_user, 'email', str(current_user.id))

    with _heartbeat_lock:
        entry = _active_mesa_users.get(tenant_key)

    if not entry:
        return {"locked": False}

    # Check expiry
    if entry["expires_at"] < _dt.now(_tz.utc):
        with _heartbeat_lock:
            _active_mesa_users.pop(tenant_key, None)
        return {"locked": False}

    # Check session_id discrepancy first (handles shared logins e.g. comercial@promaflex.com.br)
    holder_session_id = entry.get("session_id")
    if holder_session_id and session_id:
        if holder_session_id == session_id:
            return {"locked": False}
        else:
            return {
                "locked": True,
                "holder_name": entry["user_name"],
                "holder_email": entry["user_email"],
                "since": entry["expires_at"].strftime("%H:%M")
            }

    # Fallback email comparison for legacy callers without session_id
    if entry["user_email"] == caller_email:
        return {"locked": False}

    return {
        "locked": True,
        "holder_name": entry["user_name"],
        "holder_email": entry["user_email"],
        "since": entry["expires_at"].strftime("%H:%M")
    }


@router.delete("/mesa-heartbeat")
def release_mesa_heartbeat(
    session_id: Optional[str] = None,
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Release the heartbeat lock immediately (called on page unmount).
    """
    tenant_key = str(current_user.tenant_id)
    caller_email = getattr(current_user, 'email', str(current_user.id))
    with _heartbeat_lock:
        entry = _active_mesa_users.get(tenant_key)
        if entry:
            holder_session_id = entry.get("session_id")
            if holder_session_id and session_id:
                if holder_session_id == session_id:
                    _active_mesa_users.pop(tenant_key, None)
            elif entry["user_email"] == caller_email:
                _active_mesa_users.pop(tenant_key, None)
    return {"success": True}


@router.get("/pending-s3-files")
async def get_pending_s3_files(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all unprocessed and recent processed files in the S3 bucket with parsed date and metadata.
    """
    from backend.services.s3_service import S3Service
    import re
    
    s3_service = S3Service(db)
    if not s3_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="S3 service not configured. Please check environment variables (S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET_NAME)."
        )
        
    try:
        files = s3_service.list_new_files()
        pending = []
        
        for f in files:
            key = f['key']
            filename = f['filename']
            size = f['size']
            last_modified = f.get('last_modified')
            is_processed = f.get('is_processed', False)
            
            # Parse date from name e.g. Exportacao_20260712_200000.xlsx
            match = re.search(r"Exportacao_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})", filename)
            if match:
                year, month, day, hour, minute, second = match.groups()
                parsed_date = f"{day}/{month}/{year} às {hour}:{minute}"
            else:
                # Fallback using last modified timestamp
                parsed_date = last_modified.strftime("%d/%m/%Y às %H:%M") if last_modified else "Desconhecida"
                
            is_empty_template = size <= 3500
            
            pending.append({
                "filename": filename,
                "file_key": key,
                "parsed_date": parsed_date,
                "size_bytes": size,
                "is_empty_template": is_empty_template,
                "is_processed": is_processed
            })
            
        return pending
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar arquivos do S3: {str(e)}"
        )


@router.post("/sync-s3")
async def sync_s3_bucket(
    req: SyncS3Request,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Sincroniza apenas os arquivos selecionados do bucket S3.
    Suporta tanto arquivos novos no root quanto re-processamento de arquivos em processed/.
    """
    from backend.services.s3_service import S3Service
    import logging
    
    logger = logging.getLogger("backend.services.s3_service")
    s3_service = S3Service(db)
    
    if not s3_service.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="S3 service not configured. Please check environment variables (S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET_NAME)."
        )
        
    result = {
        'success': True,
        'files_processed': 0,
        'files_failed': 0,
        'pos_imported': [],
        'po_list': [],          # ← accumulated staging data, returned to frontend
        'errors': []
    }
    
    try:
        # Get list of files in S3 (root + processed)
        all_s3_files = s3_service.list_new_files()
        requested_ids = set(req.file_keys or req.filenames or [])
        
        # Filter to only keep selected files matching filename or file_key
        selected_files = [
            f for f in all_s3_files
            if f['filename'] in requested_ids or f['key'] in requested_ids
        ]
        
        for file_info in selected_files:
            file_key = file_info['key']
            filename = file_info['filename']
            size = file_info['size']
            is_processed = file_info.get('is_processed', False) or file_key.startswith('processed/')
            
            # ── Empty weekend template: archive if not already in processed ──────
            if size <= 3500:
                try:
                    logger.info(f"[S3→STAGING] {filename} is a weekend template.")
                    if not is_processed:
                        s3_service.move_to_processed(file_key)
                    result['files_processed'] += 1
                except Exception as e:
                    result['files_failed'] += 1
                    result['errors'].append(f"{filename} (archive failed): {str(e)}")
                continue
            
            # ── Data file: parse into staging po_list, archive if in root ───────
            try:
                logger.info(f"[S3→STAGING] Parsing {filename} (is_processed={is_processed}) for Mesa de Conferência staging.")
                file_content, _ = s3_service.download_file(file_key)
                
                # Create import request
                import_request = ImportRequest(
                    file_content=file_content,
                    file_name=filename,
                    mapping=s3_service.get_default_mapping(),
                    tenant_id=str(current_user.tenant_id),
                    user_id=str(current_user.id)
                )
                
                # import_po() parses the Excel and returns po_list
                import_response = s3_service.import_service.import_po(import_request)
                
                if import_response.success:
                    # Move to processed folder only if file came from bucket root
                    if not is_processed:
                        s3_service.move_to_processed(file_key)
                        
                    result['files_processed'] += 1
                    
                    # Accumulate po_list entries so all files merge into one staging batch
                    if import_response.po_list:
                        result['po_list'].extend(import_response.po_list)
                        for po in import_response.po_list:
                            result['pos_imported'].append(po.get('po_number', 'N/A'))
                    elif import_response.items:
                        # Legacy single-PO fallback
                        result['po_list'].append({
                            'po_number':    import_response.po_number,
                            'client_name':  import_response.client_name,
                            'business_unit': None,
                            'items':        [item.model_dump() for item in import_response.items],
                            'po_total_value': getattr(import_response, 'po_total_value', None),
                            'has_integrity_error': getattr(import_response, 'has_integrity_error', False),
                            'integrity_error_message': getattr(import_response, 'integrity_error_message', None),
                        })
                        result['pos_imported'].append(import_response.po_number or 'N/A')
                else:
                    result['files_failed'] += 1
                    result['errors'].append(f"{filename}: {import_response.message}")
            except Exception as e:
                result['files_failed'] += 1
                result['errors'].append(f"{filename}: {str(e)}")
                    
        # Partial failure is still a partial success
        if result['files_failed'] > 0 and result['files_processed'] == 0:
            result['success'] = False

        # ── Upsert staging session so other operators can load this batch ──────
        if result['po_list']:
            try:
                _upsert_staging_session(
                    db=db,
                    tenant_id=str(current_user.tenant_id),
                    po_list=result['po_list'],
                    updated_by=getattr(current_user, 'email', str(current_user.id))
                )
            except Exception as upsert_err:
                logger.warning(f"[S3→STAGING] Failed to upsert staging session: {upsert_err}")

        return result
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao sincronizar com S3: {str(e)}"
        )


@router.post("/finance-decision", response_model=FinanceDecisionResponse)
def record_finance_decision(
    request: FinanceDecisionRequest,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Record a Finance Approval or Rejection decision for a staging item.

    **Business Rules:**
    - The item must belong to the current user's tenant (enforced).
    - Justification must be at least 20 characters.
    - Creates an immutable AuditLog v2 entry with `tenant_id` in the SHA-256 hash.
    - The `justification` is stored in `extra_data` for full traceability.

    **Status transitions:**
    - APPROVE → item status becomes `FINANCE_APPROVED`
    - REJECT  → item status becomes `FINANCE_REJECTED`

    **Returns:**
    - Decision confirmation with audit log ID and hash prefix
    """
    # ─── 1. Resolve item ────────────────────────────────────────────────────────────
    item_uuid = uuid.UUID(request.item_id)  # already validated by Pydantic
    tenant_uuid = uuid.UUID(str(current_user.tenant_id))
    user_uuid = uuid.UUID(str(current_user.id))

    item: OrderItem | None = (
        db.query(OrderItem)
        .filter(
            OrderItem.id == item_uuid,
            OrderItem.tenant_id == tenant_uuid  # multi-tenant guard
        )
        .first()
    )

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Item {request.item_id!r} not found or does not belong "
                f"to this tenant."
            )
        )

    # ─── 2. Determine new status ───────────────────────────────────────────────────
    from_status = item.status_item
    new_status = (
        "FINANCE_APPROVED"
        if request.decision == FinanceDecision.APPROVE
        else "FINANCE_REJECTED"
    )

    # ─── 3. Create AuditLog v2 entry ──────────────────────────────────────────────
    now = datetime.now(timezone.utc)

    # Fetch the previous hash from the most recent audit log for this item (for chaining)
    previous_log = (
        db.query(AuditLog)
        .filter(AuditLog.item_id == item_uuid)
        .order_by(AuditLog.created_at.desc())
        .first()
    )
    previous_hash: str | None = previous_log.hash if previous_log else None

    # Compute v2 hash — includes tenant_id to prevent cross-tenant collisions
    computed_hash = AuditLog.calculate_hash_v2(
        tenant_id=tenant_uuid,
        item_id=item_uuid,
        from_status=from_status,
        to_status=new_status,
        timestamp=now,
        previous_hash=previous_hash,
        changed_by=user_uuid
    )

    audit_log = AuditLog(
        id=uuid.uuid4(),
        item_id=item_uuid,
        from_status=from_status,
        to_status=new_status,
        hash=computed_hash,
        previous_hash=previous_hash,
        hash_version=AuditLog.HASH_VERSION_CURRENT,  # v2
        is_exception=(request.decision == FinanceDecision.REJECT),
        justification=request.justification,
        changed_by=user_uuid,
        created_at=now,
        extra_data={
            "decision": request.decision.value,
            "justification": request.justification,
            "finance_reviewer_id": str(user_uuid),
            "finance_reviewer_name": getattr(current_user, 'name', str(user_uuid)),
            "workflow": "FINANCE_APPROVAL"
        }
    )

    # ─── 4. Persist ──────────────────────────────────────────────────────────────
    try:
        item.status_item = new_status
        db.add(audit_log)
        db.commit()
        db.refresh(audit_log)
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record finance decision: {str(exc)}"
        ) from exc

    # ─── 5. Return confirmation ───────────────────────────────────────────────────────
    action_label = "aprovado" if request.decision == FinanceDecision.APPROVE else "rejeitado"
    return FinanceDecisionResponse(
        success=True,
        message=(
            f"Item {request.item_id[:8]}... {action_label} financeiramente. "
            f"Audit log v2 registrado."
        ),
        item_id=request.item_id,
        decision=request.decision,
        new_status=new_status,
        audit_log_id=str(audit_log.id),
        audit_hash=computed_hash[:16]  # prefix only — never expose full hash in response
    )


@router.post("/confirm-staging")
def confirm_staging(
    payload: ConfirmStagingPayload,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Confirm and persist staging items to the production database.
    
    **Business Rules:**
    - Cleanly deletes any existing PO for the tenant with matching `po_number` to prevent unique constraint failures.
    - If any item in the PO is BLOQUEADO and has a justification, the PO's macro status transitions to 'ANALISE_CREDITO'.
    - Implements blockchain-hash chained v2 AuditLogs for items placed under credit analysis.
    - Packs non-column ONET spreadsheet fields into JSONB extra_metadata.
    """
    tenant_uuid = uuid.UUID(str(current_user.tenant_id))
    user_uuid = uuid.UUID(str(current_user.id))

    try:
        try:
            with open("uvicorn_live_import.log", "w", encoding="utf-8") as f:
                f.truncate(0)
        except Exception:
            pass

        for po in payload.pos:
            # 1. Cleanly delete existing PO with identical po_number under this tenant
            existing_po = (
                db.query(PurchaseOrder)
                .filter(
                    PurchaseOrder.po_number == po.po_number,
                    PurchaseOrder.tenant_id == tenant_uuid
                )
                .first()
            )
            if existing_po:
                db.delete(existing_po)
                db.flush()

            # 2. Determine macro status
            has_blocked_item = any(
                item.block_status == "BLOQUEADO"
                or (
                    item.extra_metadata is not None
                    and getattr(item.extra_metadata, "finance_justification", None) is not None
                    and str(item.extra_metadata.finance_justification).strip() != ""
                )
                for item in po.items
            )

            # FF-HARDENING-004: Detect financial mismatch for this PO
            # (same arithmetic used in import_schema.py validate_po_integrity)
            items_with_totals = [it for it in po.items if it.item_total_value is not None]
            if po.po_total_value is not None and items_with_totals:
                from decimal import Decimal as _D
                _calc_sum = sum(
                    float(it.item_total_value or 0) + float(it.ipi or 0)
                    for it in items_with_totals
                )
                _po_total = float(po.po_total_value)
                has_financial_mismatch = abs(_calc_sum - _po_total) > 0.01
                _discrepancy_brl = round(abs(_calc_sum - _po_total), 2)
                _calculated_sum_brl = round(_calc_sum, 2)
                _po_total_brl = round(_po_total, 2)
            else:
                has_financial_mismatch = False
                _discrepancy_brl = 0.0
                _calculated_sum_brl = 0.0
                _po_total_brl = 0.0

            # Extract metadata flags BEFORE routing decision (FF-HARDENING-015 Item 3)
            is_personalized = any(item.extra_metadata.is_personalized for item in po.items if item.extra_metadata)
            is_new_client = any(item.extra_metadata.is_new_client for item in po.items if item.extra_metadata)
            is_export = any(item.extra_metadata.is_export for item in po.items if item.extra_metadata)
            is_replacement = any(item.extra_metadata.is_replacement for item in po.items if item.extra_metadata)
            is_triangular = any(getattr(item.extra_metadata, 'is_triangular', False) for item in po.items if item.extra_metadata)
            is_estoque = any(getattr(item.extra_metadata, 'is_estoque', False) for item in po.items if item.extra_metadata)

            # Status routing — FF-HARDENING-013 Item 2: ALL confirmed POs route strictly to PCP.
            # Exception FF-HARDENING-015 Item 3: Triangular/Remessa or Material de Estoque POs
            # skip manufacturing and route directly to BILLING (Faturamento).
            if is_triangular or is_estoque:
                po_status_macro = PurchaseOrder.STATUS_BILLING  # → Faturamento column
            elif has_blocked_item:
                po_status_macro = PurchaseOrder.STATUS_FINANCE
            else:
                po_status_macro = PurchaseOrder.STATUS_APPROVED  # → PCP column

            # 3. Create new PurchaseOrder
            # ONET 2026-07-01 DATE ROLE ALIGNMENT:
            #   billing_date (Dt.Faturamento) → contractual delivery = SLA base = expected_delivery_date [9.1]
            #   delivery_date (Dt.Entrega)    → order entry/receipt date (stored separately)
            #   order_date (Data do Pedido)   → original order creation date
            first_item_sla_delivery = None  # Dt.Faturamento → expected_delivery_date
            first_item_entry_date = None    # Dt.Entrega    → order entry date
            first_item_order_date = None    # Data do Pedido → original order date
            # Carrier fields → from first item that has them, promoted to PO level
            po_carrier_code = None
            po_carrier_name = None
            if po.items:
                for item in po.items:
                    if first_item_sla_delivery is None and item.billing_date:
                        first_item_sla_delivery = item.billing_date
                    if first_item_entry_date is None and item.delivery_date:
                        first_item_entry_date = item.delivery_date
                    if first_item_order_date is None and item.order_date:
                        first_item_order_date = item.order_date
                    if po_carrier_code is None and item.carrier_code:
                        po_carrier_code = item.carrier_code
                    if po_carrier_name is None and item.carrier_name:
                        po_carrier_name = item.carrier_name

            customization_notes = None
            attachment_path = None
            for item in po.items:
                if item.extra_metadata:
                    if not customization_notes and item.extra_metadata.customization_notes:
                        customization_notes = item.extra_metadata.customization_notes
                    if not attachment_path and item.extra_metadata.attachment_path:
                        attachment_path = item.extra_metadata.attachment_path

            # Calculate total freight cost from items if freight_cost + additional_costs is 0
            original_freight = po.freight_cost + po.additional_costs
            if original_freight == 0 and po.items:
                original_freight = sum(float(item.freight or 0.0) for item in po.items)

            # Upsert client preference memory
            from backend.models import ClientPreference
            from sqlalchemy import select
            pref_stmt = select(ClientPreference).where(
                ClientPreference.tenant_id == tenant_uuid,
                ClientPreference.client_name == po.client_name
            )
            existing_pref = db.execute(pref_stmt).scalar_one_or_none()
            if existing_pref:
                existing_pref.business_unit = po.business_unit
            else:
                new_pref = ClientPreference(
                    tenant_id=tenant_uuid,
                    client_name=po.client_name,
                    business_unit=po.business_unit
                )
                db.add(new_pref)
            db.flush()  # sends ClientPreference INSERT on the current connection

            # ── Pre-assign PO UUID in Python so items can reference it before commit
            new_po_id = uuid.uuid4()
            new_po = PurchaseOrder(
                id=new_po_id,
                tenant_id=tenant_uuid,
                po_number=po.po_number,
                status_macro=po_status_macro,
                created_by=user_uuid,
                shipping_cost=original_freight,
                po_total_value=po.po_total_value,
                partition_metadata={
                    "client_name": po.client_name,
                    # SLA base: Dt.Faturamento (billing_date) → expected_delivery_date [9.1]
                    "expected_delivery_date": first_item_sla_delivery,
                    # Supplementary dates stored for reference / audit
                    "order_entry_date": first_item_entry_date,    # Dt.Entrega
                    "order_date": first_item_order_date,           # Data do Pedido
                    "packaging_type": po.packaging_type,
                    "is_personalized": is_personalized,
                    "is_new_client": is_new_client,
                    "is_export": is_export,
                    "is_replacement": is_replacement,
                    "is_triangular": is_triangular,               # FF-HARDENING-015 Item 3
                    "is_estoque": is_estoque,                     # FF-HARDENING-015 Item 3
                    "customization_notes": customization_notes,
                    "attachment_path": attachment_path,
                    "additional_costs": po.additional_costs,
                    "business_unit": po.business_unit,
                    # Carrier fields → default Faturamento stage carrier dropdown in UI
                    "carrier_code": po_carrier_code,
                    "carrier_name": po_carrier_name,
                }
            )
            db.add(new_po)
            # ── flush() serializes the PO INSERT on the current connection so that
            # subsequent item flushes can satisfy the order_items_po_id_fkey FK
            # within the same open transaction. All operations share one connection.
            db.flush()
            print(f"MIGRATION/DEPLOY PROOF: PO {new_po.po_number} flushed (not yet committed).", flush=True)

            # FF-HARDENING-004 audit log: track the mismatch decision for the first item after it is flushed
            # (The audit log item_id is an FK to order_items, so we must flush the first item first.)
            _ff004_first_item_id: uuid.UUID | None = None

            # 4. Process each item
            for item in po.items:
                is_item_blocked = (
                    item.block_status == "BLOQUEADO"
                    or (
                        item.extra_metadata is not None
                        and getattr(item.extra_metadata, "finance_justification", None) is not None
                        and str(item.extra_metadata.finance_justification).strip() != ""
                    )
                )
                item_status = "ANALISE_CREDITO" if is_item_blocked else "PENDING"

                # Merge all ONET fields into a single extra_metadata dictionary
                extra_metadata_dict = {
                    "is_personalized": item.extra_metadata.is_personalized if item.extra_metadata else False,
                    "is_new_client": item.extra_metadata.is_new_client if item.extra_metadata else False,
                    "is_export": item.extra_metadata.is_export if item.extra_metadata else False,
                    "is_replacement": item.extra_metadata.is_replacement if item.extra_metadata else False,
                    "is_triangular": getattr(item.extra_metadata, 'is_triangular', False) if item.extra_metadata else False,   # FF-HARDENING-015
                    "is_estoque": getattr(item.extra_metadata, 'is_estoque', False) if item.extra_metadata else False,           # FF-HARDENING-015
                    "customization_notes": item.extra_metadata.customization_notes if item.extra_metadata else None,
                    "attachment_path": item.extra_metadata.attachment_path if item.extra_metadata else None,
                    "attachment_filename": item.extra_metadata.attachment_filename if item.extra_metadata else None,
                    "apply_sla_reduction": item.extra_metadata.apply_sla_reduction if item.extra_metadata else False,
                    "finance_justification": item.extra_metadata.finance_justification if item.extra_metadata else None,
                    "additional_costs": po.additional_costs,

                    "block_status": item.block_status,
                    "balance": item.balance,
                    "delay": item.delay,
                    "payment_terms": item.payment_terms,
                    "description": item.description,
                    "unit": item.unit,
                    "width": item.width,
                    "length": item.length,
                    "lead_time": item.lead_time,
                    # Dt.Entrega → order entry/receipt date
                    "delivery_date": item.delivery_date,
                    # Dt.Faturamento → SLA contractual delivery date [9.1]
                    "billing_date": item.billing_date,
                    # Data do Pedido → original order creation date
                    "order_date": item.order_date,
                    "icms_percent": item.icms_percent,
                    "freight": item.freight,
                    "salesperson": item.salesperson,
                    "ipi": item.ipi,

                    # ONET 2026-07-01: new structured code field
                    "codigo_estruturado": item.codigo_estruturado,

                    "client_name": po.client_name
                }

                # Pre-assign item UUID so AuditLog FK can reference it without
                # needing an intermediate flush to retrieve a DB-generated PK
                new_item_id = uuid.uuid4()
                new_item = OrderItem(
                    id=new_item_id,
                    po_id=new_po_id,
                    tenant_id=tenant_uuid,
                    sku=item.sku,
                    quantity=item.quantity,
                    price=item.price_unit,
                    status_item=item_status,
                    unit_value=item.unit_value,
                    item_total_value=item.item_total_value,
                    is_personalized=item.extra_metadata.is_personalized if item.extra_metadata else False,
                    is_new_client=item.extra_metadata.is_new_client if item.extra_metadata else False,
                    customization_notes=item.extra_metadata.customization_notes if item.extra_metadata else None,
                    attachment_path=item.extra_metadata.attachment_path if item.extra_metadata else None,
                    extra_metadata=extra_metadata_dict
                )
                db.add(new_item)
                db.flush()  # sends item INSERT; FK satisfied because PO was flushed above

                # FF-HARDENING-004: Write the mismatch decision audit log using the FIRST item's UUID as anchor
                # (AuditLog.item_id is a FK to order_items, so the item must be flushed first)
                if has_financial_mismatch and _ff004_first_item_id is None:
                    _ff004_first_item_id = new_item_id
                    _now_ff004 = datetime.now(timezone.utc)
                    _approver_email = getattr(current_user, 'email', str(user_uuid))
                    _approver_name = getattr(current_user, 'name', None) or _approver_email

                    if payload.financial_override:
                        # CASE A: operator approved the mismatch → PCP column
                        _ff004_justification = "CONFERIDO - APROVADO COM DIVERGENCIA (IPI)"
                        _ff004_decision = "FINANCIAL_OVERRIDE_APPROVED"
                        _ff004_routed_to = "APPROVED (PCP)"
                    else:
                        # CASE B: mismatch detected but no override — still routed to PCP
                        # (FF-HARDENING-013: COMPLETED routing removed; all POs go to PCP)
                        _ff004_justification = "CONFERIDO - DIVERGENCIA IPI DETECTADA (ROTEADO PARA PCP)"
                        _ff004_decision = "FINANCIAL_MISMATCH_NOTED_ROUTED_PCP"
                        _ff004_routed_to = "APPROVED (PCP)"  # no longer COMPLETED

                    _ff004_hash = AuditLog.calculate_hash_v2(
                        tenant_id=tenant_uuid,
                        item_id=new_item_id,
                        from_status=None,
                        to_status="CONFERIDO",
                        timestamp=_now_ff004,
                        previous_hash=None,
                        changed_by=user_uuid
                    )
                    _ff004_audit = AuditLog(
                        id=uuid.uuid4(),
                        item_id=new_item_id,
                        from_status=None,
                        to_status="CONFERIDO",
                        hash=_ff004_hash,
                        previous_hash=None,
                        hash_version=AuditLog.HASH_VERSION_CURRENT,
                        is_exception=(not payload.financial_override),
                        justification=_ff004_justification,
                        changed_by=user_uuid,
                        created_at=_now_ff004,
                        extra_data={
                            "decision": _ff004_decision,
                            "po_number": po.po_number,
                            "approver_id": str(user_uuid),
                            "approver_name": _approver_name,
                            "approver_email": _approver_email,
                            "discrepancy_amount_brl": _discrepancy_brl,
                            "calculated_sum_brl": _calculated_sum_brl,
                            "po_total_value_brl": _po_total_brl,
                            "routed_to": _ff004_routed_to,
                            "workflow": "FF_HARDENING_004_MISMATCH_DECISION",
                            "timestamp": _now_ff004.isoformat()
                        }
                    )
                    db.add(_ff004_audit)
                    db.flush()
                    print(
                        f"[FF-HARDENING-004] Mismatch audit log written for PO {po.po_number} | "
                        f"Decision: {_ff004_decision} | Discrepancy: R$ {_discrepancy_brl:.2f} | "
                        f"Routed to: {_ff004_routed_to}",
                        flush=True
                    )

                # 5. Create chained AuditLog if item is blocked
                if is_item_blocked:

                    now = datetime.now(timezone.utc)
                    computed_hash = AuditLog.calculate_hash_v2(
                        tenant_id=tenant_uuid,
                        item_id=new_item_id,
                        from_status=None,
                        to_status="ANALISE_CREDITO",
                        timestamp=now,
                        previous_hash=None,
                        changed_by=user_uuid
                    )

                    audit_log = AuditLog(
                        id=uuid.uuid4(),
                        item_id=new_item_id,
                        from_status=None,
                        to_status="ANALISE_CREDITO",
                        hash=computed_hash,
                        previous_hash=None,
                        hash_version=AuditLog.HASH_VERSION_CURRENT,
                        is_exception=True,
                        justification=item.extra_metadata.finance_justification,
                        changed_by=user_uuid,
                        created_at=now,
                        extra_data={
                            "decision": "BLOCKED_ON_IMPORT",
                            "justification": item.extra_metadata.finance_justification,
                            "initiator_id": str(user_uuid),
                            "workflow": "FINANCE_BLOCK_ON_IMPORT"
                        }
                    )
                    db.add(audit_log)
                    db.flush()  # sends audit_log INSERT; item FK satisfied above

                # FF-HARDENING-015 Item 3: Write immutable CONFERIDO audit log for Triangular/Remessa or Estoque routing
                item_is_triangular = getattr(item.extra_metadata, 'is_triangular', False) if item.extra_metadata else False
                item_is_estoque = getattr(item.extra_metadata, 'is_estoque', False) if item.extra_metadata else False
                if item_is_triangular or item_is_estoque:
                    _route_type = "TRIANGULAR/REMESSA" if item_is_triangular else "MATERIAL DE ESTOQUE (E-COM)"
                    _conferido_reason = f"CONFERIDO - ROTEADO PARA FATURAMENTO ({_route_type})"
                    _now_billing = datetime.now(timezone.utc)
                    _billing_hash = AuditLog.calculate_hash_v2(
                        tenant_id=tenant_uuid,
                        item_id=new_item_id,
                        from_status=None,
                        to_status="BILLING",
                        timestamp=_now_billing,
                        previous_hash=None,
                        changed_by=user_uuid
                    )
                    _billing_audit = AuditLog(
                        id=uuid.uuid4(),
                        item_id=new_item_id,
                        from_status=None,
                        to_status="BILLING",
                        hash=_billing_hash,
                        previous_hash=None,
                        hash_version=AuditLog.HASH_VERSION_CURRENT,
                        is_exception=False,
                        justification=_conferido_reason,
                        changed_by=user_uuid,
                        created_at=_now_billing,
                        extra_data={
                            "decision": "DIRECT_TO_BILLING",
                            "route_type": _route_type,
                            "po_number": po.po_number,
                            "workflow": "FF_HARDENING_015_BILLING_ROUTING"
                        }
                    )
                    db.add(_billing_audit)
                    db.flush()
                    print(
                        f"[FF-HARDENING-015] Billing routing audit log written for PO {po.po_number} | "
                        f"Route type: {_route_type}",
                        flush=True
                    )

            # ── Single commit per PO: atomically commits ClientPreference + PurchaseOrder
            # + all OrderItems + all AuditLogs in one COMMIT round-trip.
            # All flushes above shared the same connection; the transaction is closed here.
            db.commit()
            db.refresh(new_po)
            success_msg = f"SUCCESS: PO {po.po_number} saved to database"
            print(success_msg, flush=True)
            try:
                with open("uvicorn_live_import.log", "a", encoding="utf-8") as f:
                    f.write(success_msg + "\n")
            except Exception:
                pass

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao salvar staging no banco: {str(exc)}"
        ) from exc

    # ── Delete active staging session after successful production commit ──────
    try:
        from sqlalchemy import select as _sel_cs
        import uuid as _uuid_cs
        _t_uuid = _uuid_cs.UUID(str(current_user.tenant_id))
        _sess = db.execute(
            _sel_cs(StagingSession).where(StagingSession.tenant_id == _t_uuid)
        ).scalar_one_or_none()
        if _sess:
            db.delete(_sess)
            db.commit()
    except Exception:
        pass  # Cleanup is best-effort; production data is already committed

    return {
        "success": True,
        "message": f"Mesa de conferência confirmada com sucesso. {len(payload.pos)} pedido(s) importado(s)."
    }


@router.post("/cancel-staging", status_code=status.HTTP_201_CREATED)
def cancel_staging_po(
    payload: CancelStagingPayload,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Persist a Mesa de Conferência cancellation for a PO that does NOT yet have a DB record.

    When an operator cancels a staging PO (parsed from ONET, not yet confirmed to DB), this
    endpoint creates a permanent CANCELLED record so the cancellation appears in the
    GET /api/reports/cancellations-export report.

    Flow:
        1. If a PO with this po_number already exists for the tenant → update it to CANCELLED
           (idempotent guard: handles accidental double-clicks or retry).
        2. Otherwise INSERT a new PurchaseOrder with status_macro=CANCELLED.
        3. Create OrderItems from payload.items (required for AuditLog FK).
        4. Write an AuditLog entry per item with action MESA_CANCELADO.
        5. Commit atomically.

    Security: Strictly scoped to current_user.tenant_id.
    """
    tenant_uuid = uuid.UUID(str(current_user.tenant_id))
    user_uuid   = uuid.UUID(str(current_user.id))
    now_utc     = datetime.now(tz=timezone.utc)

    try:
        # ── Idempotency guard: PO already in DB ───────────────────────────────
        existing_po = (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.tenant_id == tenant_uuid,
                PurchaseOrder.po_number == payload.po_number,
            )
            .first()
        )

        if existing_po:
            # Update to CANCELLED and store justification, then return early.
            existing_po.status_macro            = "CANCELLED"
            existing_po.sla_justification_text  = payload.justification
            existing_po.sla_justification_user  = current_user.email or current_user.name
            existing_po.sla_justification_at    = now_utc
            existing_po.sla_justification_category = "CANCELAMENTO"
            db.commit()
            return {
                "success": True,
                "po_id": str(existing_po.id),
                "po_number": existing_po.po_number,
                "action": "updated_to_cancelled",
            }

        # ── Build partition_metadata ──────────────────────────────────────────
        partition_metadata = {
            "client_name": payload.client_name or "",
            "cancelled_at": now_utc.isoformat(),
            "cancelled_by": current_user.email or current_user.name,
            "source": "MESA_CONFERENCIA",
        }

        # ── INSERT CANCELLED PO ───────────────────────────────────────────────
        new_po = PurchaseOrder(
            id=uuid.uuid4(),
            tenant_id=tenant_uuid,
            po_number=payload.po_number,
            status_macro="CANCELLED",
            po_total_value=payload.po_total_value,
            partition_metadata=partition_metadata,
            sla_justification_text=payload.justification,
            sla_justification_user=current_user.email or current_user.name,
            sla_justification_at=now_utc,
            sla_justification_category="CANCELAMENTO",
            created_by=user_uuid,
        )
        db.add(new_po)
        db.flush()  # get new_po.id before creating items

        # ── INSERT items + AuditLogs ──────────────────────────────────────────
        # AuditLog.item_id is NOT NULL, so we must create at least one item.
        # Use the payload items if provided; otherwise create a single sentinel item.
        items_to_create = payload.items or [
            CancelStagingItemSchema(sku="N/A", quantity=1.0, price=0.0)
        ]

        for item_data in items_to_create:
            new_item = OrderItem(
                id=uuid.uuid4(),
                po_id=new_po.id,
                tenant_id=tenant_uuid,
                sku=item_data.sku,
                quantity=max(float(item_data.quantity or 1.0), 0.000001),
                price=float(item_data.price or 0.0),
                status_item="CANCELLED",
                is_personalized=False,
                extra_metadata={
                    "codigo_estruturado": item_data.codigo_estruturado or "",
                    "client_name": payload.client_name or "",
                    "largura": item_data.largura,
                    "comprimento": item_data.comprimento,
                    "cancel_source": "MESA_CONFERENCIA",
                },
            )
            db.add(new_item)
            db.flush()  # get new_item.id for AuditLog

            audit_hash = AuditLog.calculate_hash_v2(
                tenant_id=tenant_uuid,
                item_id=new_item.id,
                from_status=None,
                to_status="CANCELLED",
                timestamp=now_utc,
                previous_hash=None,
                changed_by=user_uuid,
            )
            audit = AuditLog(
                id=uuid.uuid4(),
                item_id=new_item.id,
                from_status=None,
                to_status="CANCELLED",
                hash=audit_hash,
                previous_hash=None,
                is_exception=True,
                justification=payload.justification,
                changed_by=user_uuid,
                hash_version=AuditLog.HASH_VERSION_CURRENT,
                extra_data={
                    "action": "MESA_CANCELADO",
                    "po_number": new_po.po_number,
                    "source": "MESA_CONFERENCIA",
                    "cancelled_by": current_user.email or current_user.name,
                },
            )
            db.add(audit)

        db.commit()
        db.refresh(new_po)

        return {
            "success": True,
            "po_id": str(new_po.id),
            "po_number": new_po.po_number,
            "action": "cancelled_and_persisted",
            "items_created": len(items_to_create),
        }

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao registrar cancelamento: {str(exc)}",
        ) from exc
