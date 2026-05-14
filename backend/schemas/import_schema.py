"""
FlexFlow Import Schemas
Pydantic schemas for validating Excel/CSV import data with dynamic mapping.
"""

from typing import Dict, List, Optional, Any
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum


class ImportFieldType(str, Enum):
    """Types of fields that can be imported - 19-field ONET structure"""
    # Core identification fields
    PO_NUMBER = "po_number"  # Pedido
    CLIENT_NAME = "client_name"  # Cliente
    SKU = "sku"  # SKU
    DESCRIPTION = "description"  # Descrição
    
    # Quantity and unit fields
    QUANTITY = "quantity"  # Qtd
    UNIT = "unit"  # Unidade
    
    # Dimensional fields
    WIDTH = "width"  # Largura
    LENGTH = "length"  # Comprimento
    
    # Timeline fields
    LEAD_TIME = "lead_time"  # Lead Time
    DELIVERY_DATE = "delivery_date"  # Data Entrega
    BILLING_DATE = "billing_date"  # Data Faturamento
    
    # Financial/Tax fields
    ICMS_PERCENT = "icms_percent"  # % ICMS
    IPI = "ipi"  # IPI
    FREIGHT = "freight"  # Frete
    PAYMENT_TERMS = "payment_terms"  # Condição Pagamento
    
    # Status/Control fields
    BLOCK_STATUS = "block_status"  # Bloqueio
    BALANCE = "balance"  # Saldo
    DELAY = "delay"  # Atraso
    SALESPERSON = "salesperson"  # Vendedor
    
    # Legacy cost fields (kept for backward compatibility)
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
        """
        Ensure minimum required fields are mapped.
        
        For the 19-field ONET structure, only core fields are mandatory:
        - PO Number, Client Name, SKU, Quantity
        
        All other fields (description, dimensions, dates, taxes, costs) are optional
        to support flexible import scenarios.
        """
        # Minimum required fields for any import
        required_fields = {
            ImportFieldType.PO_NUMBER,
            ImportFieldType.CLIENT_NAME,
            ImportFieldType.SKU,
            ImportFieldType.QUANTITY,
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
    Supports the full 19-field ONET structure with optional fields.
    """
    # Core required fields
    sku: str = Field(..., min_length=1, max_length=100)
    quantity: int = Field(..., gt=0, description="Quantity must be positive")
    
    # Optional ONET fields
    description: Optional[str] = Field(None, max_length=500, description="Product description")
    unit: Optional[str] = Field(None, max_length=10, description="Unit of measure (UN, KG, etc)")
    
    # Dimensional fields
    width: Optional[Decimal] = Field(None, ge=0, description="Width in mm")
    length: Optional[Decimal] = Field(None, ge=0, description="Length in mm")
    
    # Timeline fields
    lead_time: Optional[int] = Field(None, ge=0, description="Lead time in days")
    delivery_date: Optional[str] = Field(None, description="Delivery date (DD/MM/YYYY)")
    billing_date: Optional[str] = Field(None, description="Billing date (DD/MM/YYYY)")
    
    # Financial/Tax fields
    icms_percent: Optional[Decimal] = Field(None, ge=0, le=100, description="ICMS percentage")
    ipi: Optional[Decimal] = Field(None, ge=0, description="IPI value")
    freight: Optional[Decimal] = Field(None, ge=0, description="Freight cost")
    payment_terms: Optional[str] = Field(None, max_length=100, description="Payment terms")
    
    # Status/Control fields
    block_status: Optional[str] = Field(None, max_length=50, description="Block/Hold status")
    balance: Optional[Decimal] = Field(None, description="Balance amount")
    delay: Optional[int] = Field(None, description="Delay in days")
    salesperson: Optional[str] = Field(None, max_length=100, description="Salesperson name")
    
    # Legacy cost fields (optional for backward compatibility)
    price_unit: Optional[Decimal] = Field(None, ge=0, description="Unit price")
    cost_mp: Optional[Decimal] = Field(None, ge=0, description="Material cost")
    cost_mo: Optional[Decimal] = Field(None, ge=0, description="Labor cost")
    cost_energy: Optional[Decimal] = Field(None, ge=0, description="Energy cost")
    cost_gas: Optional[Decimal] = Field(None, ge=0, description="Gas cost")
    
    # Staging Area / Customization fields
    is_personalized: bool = Field(default=False, description="Whether item is personalized")
    is_new_client: bool = Field(default=False, description="Whether this is a new client")
    customization_notes: Optional[str] = Field(None, description="Customization description")
    attachment_path: Optional[str] = Field(None, description="Path to attachment file")
    
    # Calculated fields
    margin_item: Optional[Decimal] = Field(None, description="Item margin (calculated)")
    total_cost: Optional[Decimal] = Field(None, description="Total cost per unit (calculated)")
    
    # Validation flags
    needs_mapping: bool = Field(default=False, description="Whether SKU needs cost mapping")
    validation_errors: List[str] = Field(default_factory=list, description="Validation errors")
    
    @field_validator('sku')
    @classmethod
    def validate_sku(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("SKU cannot be empty")
        return v.strip()
    
    @model_validator(mode='after')
    def calculate_margins(self):
        """Calculate item margin and total cost if cost fields are provided"""
        # Only calculate if we have cost data
        if all([self.cost_mp is not None, self.cost_mo is not None,
                self.cost_energy is not None, self.cost_gas is not None]):
            self.total_cost = self.cost_mp + self.cost_mo + self.cost_energy + self.cost_gas
            
            # Calculate margin if we also have price
            if self.price_unit is not None:
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
