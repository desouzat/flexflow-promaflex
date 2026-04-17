"""
FlexFlow Import Router
Endpoints for file upload and import configuration.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status, Form
from sqlalchemy.orm import Session
from typing import List, Optional
import json

from backend.schemas.import_schema import (
    ImportMapping,
    ImportResponse,
    ImportRequest,
    ColumnMapping,
    ImportFieldType,
    ImportItemData
)
from backend.schemas.auth_schema import UserInfo
from backend.services.import_service import ImportService
from backend.services.file_service import FileService
from backend.database import get_db
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/api/import", tags=["Import"])


# In-memory storage for import configurations (replace with database in production)
import_configs_storage = {}


@router.post("/upload", response_model=ImportResponse)
async def upload_and_import_file(
    file: UploadFile = File(..., description="Excel or CSV file to import"),
    mapping_json: str = File(..., description="JSON string of column mapping"),
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
    
    # Execute import
    import_service = ImportService(db)
    response = import_service.import_po(import_request)
    
    if not response.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=response.message
        )
    
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
async def get_available_field_types(
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
        {
            "value": ImportFieldType.PO_NUMBER,
            "label": "PO Number",
            "description": "Purchase Order number",
            "required": True
        },
        {
            "value": ImportFieldType.CLIENT_NAME,
            "label": "Client Name",
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
            "label": "Quantity",
            "description": "Item quantity (must be positive integer)",
            "required": True
        },
        {
            "value": ImportFieldType.PRICE_UNIT,
            "label": "Unit Price",
            "description": "Price per unit (must be non-negative)",
            "required": True
        },
        {
            "value": ImportFieldType.COST_MP,
            "label": "Material Cost",
            "description": "Cost of raw materials (Matéria Prima)",
            "required": True
        },
        {
            "value": ImportFieldType.COST_MO,
            "label": "Labor Cost",
            "description": "Cost of labor (Mão de Obra)",
            "required": True
        },
        {
            "value": ImportFieldType.COST_ENERGY,
            "label": "Energy Cost",
            "description": "Energy/electricity cost",
            "required": True
        },
        {
            "value": ImportFieldType.COST_GAS,
            "label": "Gas Cost",
            "description": "Gas cost",
            "required": True
        }
    ]
    
    return {
        "field_types": field_types,
        "total": len(field_types)
    }


@router.post("/configs")
async def save_import_config(
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
async def list_import_configs(
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
async def get_import_config(
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
async def delete_import_config(
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
    
    file_service = FileService()
    
    try:
        file_path, original_filename = await file_service.save_file(
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
async def validate_staging_item(
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
