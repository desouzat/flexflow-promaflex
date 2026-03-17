"""
FlexFlow Import Schemas
Pydantic schemas for validating Excel/CSV import data with dynamic mapping.
"""

from typing import Dict, List, Optional, Any
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum


class ImportFieldType(str, Enum):
    """Types of fields that can be imported"""
    PO_NUMBER = "po_number"
    CLIENT_NAME = "client_name"
    SKU = "sku"
    QUANTITY = "quantity"
    PRICE_UNIT = "price_unit"
    COST_MP = "cost_mp"  # Matéria Prima
    COST_MO = "cost_mo"  # Mão de Obra
    COST_ENERGY = "cost_energy"  # Energia
    COST_GAS = "cost_gas"  # Gás


class ColumnMapping(BaseModel):
    """
    Maps a column from the spreadsheet to a field in the system.
    
    Example:
        {"column_name": "Número PO", "field_type": "po_number"}
    """
    column_name: str = Field(..., description="Name of the column in the spreadsheet")
    field_type: ImportFieldType = Field(..., description="Type of field this column maps to")
    
    @field_validator('column_name')
    @classmethod
    def validate_column_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Column name cannot be empty")
        return v.strip()


class ImportMapping(BaseModel):
    """
    Complete mapping configuration for an import operation.
    Defines how spreadsheet columns map to system fields.
    """
    mappings: List[ColumnMapping] = Field(..., min_length=1)
    
    @model_validator(mode='after')
    def validate_required_fields(self):
        """Ensure all required fields are mapped"""
        required_fields = {
            ImportFieldType.PO_NUMBER,
            ImportFieldType.CLIENT_NAME,
            ImportFieldType.SKU,
            ImportFieldType.QUANTITY,
            ImportFieldType.PRICE_UNIT,
            ImportFieldType.COST_MP,
            ImportFieldType.COST_MO,
            ImportFieldType.COST_ENERGY,
            ImportFieldType.COST_GAS
        }
        
        mapped_fields = {mapping.field_type for mapping in self.mappings}
        missing_fields = required_fields - mapped_fields
        
        if missing_fields:
            missing_names = [field.value for field in missing_fields]
            raise ValueError(
                f"Missing required field mappings: {', '.join(missing_names)}"
            )
        
        return self
    
    @model_validator(mode='after')
    def validate_unique_mappings(self):
        """Ensure each field type is mapped only once"""
        field_types = [mapping.field_type for mapping in self.mappings]
        if len(field_types) != len(set(field_types)):
            raise ValueError("Each field type can only be mapped once")
        
        return self
    
    def get_mapping_dict(self) -> Dict[str, ImportFieldType]:
        """Returns a dictionary mapping column names to field types"""
        return {mapping.column_name: mapping.field_type for mapping in self.mappings}


class ImportItemData(BaseModel):
    """
    Validated data for a single item in the import.
    All costs and prices are validated as positive numbers.
    """
    sku: str = Field(..., min_length=1, max_length=100)
    quantity: int = Field(..., gt=0, description="Quantity must be positive")
    price_unit: Decimal = Field(..., ge=0, description="Unit price must be non-negative")
    cost_mp: Decimal = Field(..., ge=0, description="Material cost must be non-negative")
    cost_mo: Decimal = Field(..., ge=0, description="Labor cost must be non-negative")
    cost_energy: Decimal = Field(..., ge=0, description="Energy cost must be non-negative")
    cost_gas: Decimal = Field(..., ge=0, description="Gas cost must be non-negative")
    
    # Calculated fields
    margin_item: Optional[Decimal] = Field(None, description="Item margin (calculated)")
    total_cost: Optional[Decimal] = Field(None, description="Total cost per unit (calculated)")
    
    @field_validator('sku')
    @classmethod
    def validate_sku(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("SKU cannot be empty")
        return v.strip()
    
    @model_validator(mode='after')
    def calculate_margins(self):
        """Calculate item margin and total cost"""
        self.total_cost = self.cost_mp + self.cost_mo + self.cost_energy + self.cost_gas
        self.margin_item = self.price_unit - self.total_cost
        return self


class ImportPOData(BaseModel):
    """
    Validated data for a complete Purchase Order import.
    Contains PO header information and all items.
    """
    po_number: str = Field(..., min_length=1, max_length=100)
    client_name: str = Field(..., min_length=1, max_length=255)
    items: List[ImportItemData] = Field(..., min_length=1)
    
    # Calculated fields
    total_value: Optional[Decimal] = Field(None, description="Total PO value (calculated)")
    total_cost: Optional[Decimal] = Field(None, description="Total PO cost (calculated)")
    margin_global: Optional[Decimal] = Field(None, description="Global PO margin (calculated)")
    margin_percentage: Optional[Decimal] = Field(None, description="Margin percentage (calculated)")
    
    @field_validator('po_number')
    @classmethod
    def validate_po_number(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("PO number cannot be empty")
        return v.strip()
    
    @field_validator('client_name')
    @classmethod
    def validate_client_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Client name cannot be empty")
        return v.strip()
    
    @model_validator(mode='after')
    def calculate_totals(self):
        """Calculate total values and global margin"""
        if not self.items:
            raise ValueError("PO must have at least one item")
        
        # Calculate totals
        self.total_value = sum(
            item.price_unit * item.quantity for item in self.items
        )
        
        self.total_cost = sum(
            item.total_cost * item.quantity for item in self.items
        )
        
        self.margin_global = self.total_value - self.total_cost
        
        # Calculate margin percentage
        if self.total_value > 0:
            self.margin_percentage = (self.margin_global / self.total_value) * 100
        else:
            self.margin_percentage = Decimal(0)
        
        return self


class ImportRowError(BaseModel):
    """Details about an error in a specific row"""
    row_number: int = Field(..., description="Row number in the spreadsheet (1-indexed)")
    column_name: Optional[str] = Field(None, description="Column where error occurred")
    field_type: Optional[ImportFieldType] = Field(None, description="Field type that failed validation")
    error_message: str = Field(..., description="Description of the error")
    raw_value: Optional[Any] = Field(None, description="The raw value that caused the error")


class ImportValidationResult(BaseModel):
    """
    Result of validating import data.
    Contains either validated data or detailed error information.
    """
    success: bool = Field(..., description="Whether validation succeeded")
    po_data: Optional[ImportPOData] = Field(None, description="Validated PO data if successful")
    errors: List[ImportRowError] = Field(default_factory=list, description="List of validation errors")
    total_rows_processed: int = Field(..., description="Total number of rows processed")
    valid_rows: int = Field(0, description="Number of valid rows")
    invalid_rows: int = Field(0, description="Number of invalid rows")
    
    @model_validator(mode='after')
    def validate_consistency(self):
        """Ensure result is consistent"""
        if self.success and not self.po_data:
            raise ValueError("Success must have po_data")
        if not self.success and not self.errors:
            raise ValueError("Failure must have errors")
        return self


class ImportRequest(BaseModel):
    """
    Request to import data from a spreadsheet.
    Contains the file data and column mappings.
    """
    file_content: bytes = Field(..., description="Raw file content (Excel or CSV)")
    file_name: str = Field(..., description="Name of the file")
    mapping: ImportMapping = Field(..., description="Column mapping configuration")
    tenant_id: str = Field(..., description="Tenant ID for multi-tenancy")
    user_id: str = Field(..., description="User ID performing the import")
    
    @field_validator('file_name')
    @classmethod
    def validate_file_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("File name cannot be empty")
        
        # Check file extension
        allowed_extensions = ['.xlsx', '.xls', '.csv']
        if not any(v.lower().endswith(ext) for ext in allowed_extensions):
            raise ValueError(
                f"Invalid file type. Allowed types: {', '.join(allowed_extensions)}"
            )
        
        return v.strip()


class ImportResponse(BaseModel):
    """
    Response after attempting to import data.
    Contains success status and details about the import.
    """
    success: bool = Field(..., description="Whether import succeeded")
    message: str = Field(..., description="Human-readable message")
    po_id: Optional[str] = Field(None, description="ID of created PO if successful")
    po_number: Optional[str] = Field(None, description="PO number if successful")
    items_imported: int = Field(0, description="Number of items imported")
    validation_result: Optional[ImportValidationResult] = Field(
        None, 
        description="Detailed validation results"
    )
    
    # Summary statistics
    total_value: Optional[Decimal] = Field(None, description="Total PO value")
    total_cost: Optional[Decimal] = Field(None, description="Total PO cost")
    margin_global: Optional[Decimal] = Field(None, description="Global margin")
    margin_percentage: Optional[Decimal] = Field(None, description="Margin percentage")
