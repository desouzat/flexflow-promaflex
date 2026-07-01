"""
FlexFlow Import Schemas
Pydantic schemas for validating Excel/CSV import data with dynamic mapping.
"""

from typing import Dict, List, Optional, Any
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum


class ImportFieldType(str, Enum):
    """Types of fields that can be imported - ONET final production schema"""
    # Core identification fields
    PO_NUMBER = "po_number"  # Pedido
    CLIENT_NAME = "client_name"  # Cliente
    SKU = "sku"  # SKU
    DESCRIPTION = "description"  # Produto (renamed from "Descr. Produto")

    # Quantity and unit fields
    QUANTITY = "quantity"  # Qtd
    UNIT = "unit"  # Unidade

    # Dimensional fields
    WIDTH = "width"  # Largura
    LENGTH = "length"  # Comprimento

    # Timeline fields
    LEAD_TIME = "lead_time"  # Lead Time
    # Dt.Entrega  → order entry/receipt date (stored in extra_metadata["delivery_date"])
    DELIVERY_DATE = "delivery_date"
    # Dt.Faturamento → contractual delivery = SLA base / expected_delivery_date [9.1]
    BILLING_DATE = "billing_date"
    # Data do Pedido → original order/creation date
    ORDER_DATE = "order_date"

    # Financial/Tax fields
    ICMS_PERCENT = "icms_percent"  # % ICMS
    IPI = "ipi"  # IPI
    FREIGHT = "freight"  # Frete
    PAYMENT_TERMS = "payment_terms"  # Condição Pagamento

    # NEW: Financial value fields (22-field structure)
    UNIT_VALUE = "unit_value"  # Vl.Unit
    ITEM_TOTAL_VALUE = "item_total_value"  # Total Item
    PO_TOTAL_VALUE = "po_total_value"  # Valor Total do Pedido

    # Status/Control fields
    BLOCK_STATUS = "block_status"  # Bloqueio
    BALANCE = "balance"  # Saldo
    DELAY = "delay"  # Atraso
    SALESPERSON = "salesperson"  # Vendedor

    # NEW: ONET final production schema fields
    # Ewaldo 2026-07-01: Codigo Estruturado → primary product code reference
    CODIGO_ESTRUTURADO = "codigo_estruturado"
    # Ewaldo 2026-07-01: Carrier fields → default Faturamento transportadora
    CARRIER_CODE = "carrier_code"   # Cod. Transportadora
    CARRIER_NAME = "carrier_name"   # Nome Transportadora

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
        
        REQUIRED FIELDS (Must be present in all imports):
        - PO Number (Pedido)
        - Client Name (Cliente)
        - SKU
        - Quantity (Qtd)
        
        OPTIONAL ONET FIELDS (19-field structure):
        - Description, Unit, Width, Length, Lead Time, Delivery Date, Billing Date,
          ICMS%, Block Status, Balance, Delay, Payment Terms, Freight, Salesperson, IPI
        
        OPTIONAL COST FIELDS (Legacy support):
        - Price Unit, Cost MP, Cost MO, Cost Energy, Cost Gas
        
        Note: Cost fields are NOT required for ONET imports. If not provided,
        they will be looked up from the material_costs table by SKU.
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
                f"Missing required field mappings: {', '.join(missing_names)}. "
                f"These 4 fields are mandatory for all imports."
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
    Supports the full 22-field ONET structure with optional fields.
    """
    # Core required fields
    sku: str = Field(..., min_length=1, max_length=100)
    quantity: float = Field(..., gt=0.0, description="Quantity must be positive")
    
    # Optional ONET fields
    description: Optional[str] = Field(None, max_length=500, description="Product description")
    unit: Optional[str] = Field(None, max_length=10, description="Unit of measure (UN, KG, etc)")
    
    # Dimensional fields
    width: Optional[Decimal] = Field(None, ge=0, description="Width in mm")
    length: Optional[Decimal] = Field(None, ge=0, description="Length in mm")
    
    # Timeline fields
    lead_time: Optional[int] = Field(None, description="Lead time in days")
    # delivery_date = Dt.Entrega (order entry/receipt date)
    delivery_date: Optional[str] = Field(None, description="Order entry date Dt.Entrega (DD/MM/YYYY)")
    # billing_date = Dt.Faturamento → SLA base / expected delivery date [9.1]
    billing_date: Optional[str] = Field(None, description="Contractual delivery date Dt.Faturamento (DD/MM/YYYY) — SLA base")
    # order_date = Data do Pedido (original PO creation/order date)
    order_date: Optional[str] = Field(None, description="Original order date Data do Pedido (DD/MM/YYYY)")

    # Financial/Tax fields
    icms_percent: Optional[Decimal] = Field(None, ge=0, le=100, description="ICMS percentage")
    ipi: Optional[Decimal] = Field(None, ge=0, description="IPI value")
    freight: Optional[Decimal] = Field(None, ge=0, description="Freight cost")
    payment_terms: Optional[str] = Field(None, max_length=100, description="Payment terms")

    # NEW: Financial value fields (22-field structure)
    unit_value: Optional[Decimal] = Field(None, ge=0, description="Unit value (Vl.Unit)")
    item_total_value: Optional[Decimal] = Field(None, ge=0, description="Item total value (Total Item)")

    # Status/Control fields
    block_status: Optional[str] = Field(None, max_length=50, description="Block/Hold status")
    balance: Optional[Decimal] = Field(None, description="Balance amount")
    delay: Optional[int] = Field(None, description="Delay in days")
    salesperson: Optional[str] = Field(None, max_length=100, description="Salesperson name")

    # NEW: ONET final production schema fields (Ewaldo 2026-07-01)
    codigo_estruturado: Optional[str] = Field(None, max_length=100, description="Codigo Estruturado — primary product code reference")
    carrier_code: Optional[str] = Field(None, max_length=50, description="Cod. Transportadora")
    carrier_name: Optional[str] = Field(None, max_length=200, description="Nome Transportadora")
    
    # Legacy cost fields (optional for backward compatibility)
    price_unit: Optional[float] = None
    cost_mp: Optional[float] = None
    cost_mo: Optional[float] = None
    cost_energy: Optional[float] = None
    cost_gas: Optional[float] = None
    
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
        # If price_unit is None but unit_value is present, copy it
        if self.price_unit is None and self.unit_value is not None:
            self.price_unit = float(self.unit_value)

        # Only calculate if we have cost data
        if all([self.cost_mp is not None, self.cost_mo is not None,
                self.cost_energy is not None, self.cost_gas is not None]):
            self.total_cost = self.cost_mp + self.cost_mo + self.cost_energy + self.cost_gas
            
            # Calculate margin if we also have price
            if self.price_unit is not None:
                self.margin_item = self.price_unit - self.total_cost
        
        return self
    
    @model_validator(mode='after')
    def validate_item_total(self):
        """Validate that item_total_value matches quantity * unit_value if both are provided"""
        if self.unit_value is not None and self.item_total_value is not None:
            expected_total = Decimal(str(self.quantity)) * self.unit_value
            # Allow small tolerance for floating point differences (0.01 = 1 cent)
            tolerance = Decimal("0.01")
            difference = abs(self.item_total_value - expected_total)
            
            if difference > tolerance:
                self.validation_errors.append(
                    f"Divergência no Total Item: Esperado {expected_total:.2f} "
                    f"(Qtd {self.quantity} × Vl.Unit {self.unit_value:.2f}), "
                    f"mas encontrado {self.item_total_value:.2f}"
                )
        
        return self


class ImportPOData(BaseModel):
    """
    Validated data for a complete Purchase Order import.
    Contains PO header information and all items.
    """
    po_number: str = Field(..., min_length=1, max_length=100)
    client_name: str = Field(..., min_length=1, max_length=255)
    items: List[ImportItemData] = Field(..., min_length=1)
    business_unit: Optional[str] = Field(None, description="Business unit of the client")
    
    # NEW: PO total value from spreadsheet (22-field structure)
    po_total_value: Optional[Decimal] = Field(None, ge=0, description="PO total value from spreadsheet (Valor Total do Pedido)")
    
    # Calculated fields
    total_value: Optional[Decimal] = Field(None, description="Total PO value (calculated)")
    total_cost: Optional[Decimal] = Field(None, description="Total PO cost (calculated)")
    margin_global: Optional[Decimal] = Field(None, description="Global PO margin (calculated)")
    margin_percentage: Optional[Decimal] = Field(None, description="Margin percentage (calculated)")
    
    # Integrity check fields
    has_integrity_error: bool = Field(default=False, description="Whether PO has integrity errors")
    integrity_error_message: Optional[str] = Field(None, description="Integrity error details")
    
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
        
        # Calculate totals only if cost data is available
        # Use .get() pattern to safely handle None values
        self.total_value = sum(
            (item.price_unit or 0) * item.quantity
            for item in self.items
            if item.price_unit is not None
        )
        
        self.total_cost = sum(
            (item.total_cost or 0) * item.quantity
            for item in self.items
            if item.total_cost is not None
        )
        
        # Only calculate margin if we have both values
        if self.total_value and self.total_cost:
            self.margin_global = self.total_value - self.total_cost
            
            # Calculate margin percentage
            if self.total_value > 0:
                self.margin_percentage = (self.margin_global / self.total_value) * 100
            else:
                self.margin_percentage = Decimal(0)
        else:
            # No cost data available - set to None
            self.margin_global = None
            self.margin_percentage = None
        
        return self
    
    @model_validator(mode='after')
    def validate_po_integrity(self):
        """
        CRITICAL INTEGRITY CHECK:
        Validate that the sum of all item_total_value + IPI matches po_total_value.
        This ensures financial consistency in the PO.
        """
        if self.po_total_value is None:
            # No PO total provided, skip integrity check
            return self
        
        # Calculate sum of all item totals and their IPI
        items_with_totals = [item for item in self.items if item.item_total_value is not None]
        
        if not items_with_totals:
            # No item totals to validate
            return self
        
        calculated_sum = sum(
            item.item_total_value + (item.ipi or Decimal("0.0"))
            for item in items_with_totals
        )
        
        # Allow small tolerance for floating point differences (0.01 = 1 cent)
        tolerance = Decimal("0.01")
        difference = abs(calculated_sum - self.po_total_value)
        
        if difference > tolerance:
            self.has_integrity_error = True
            self.integrity_error_message = (
                f"Divergência de valores: Soma dos itens + IPI (R$ {calculated_sum:.2f}) "
                f"não confere com o total do pedido (R$ {self.po_total_value:.2f}). "
                f"Diferença: R$ {difference:.2f}"
            )
        else:
            self.has_integrity_error = False
            self.integrity_error_message = None
        
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
    Supports multiple POs in a single file.
    """
    success: bool = Field(..., description="Whether validation succeeded")
    po_data: Optional[ImportPOData] = Field(None, description="Validated PO data if successful (single PO - legacy)")
    po_data_list: Optional[List[ImportPOData]] = Field(None, description="List of validated PO data (multi-PO support)")
    errors: List[ImportRowError] = Field(default_factory=list, description="List of validation errors")
    total_rows_processed: int = Field(..., description="Total number of rows processed")
    valid_rows: int = Field(0, description="Number of valid rows")
    invalid_rows: int = Field(0, description="Number of invalid rows")
    
    @model_validator(mode='after')
    def validate_consistency(self):
        """Ensure result is consistent"""
        if self.success and not self.po_data and not self.po_data_list:
            raise ValueError("Success must have po_data or po_data_list")
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
    Supports multiple POs in a single file.
    """
    success: bool = Field(..., description="Whether import succeeded")
    message: str = Field(..., description="Human-readable message")
    
    # Single PO fields (legacy support)
    po_id: Optional[str] = Field(None, description="ID of created PO if successful (single PO)")
    po_number: Optional[str] = Field(None, description="PO number if successful (single PO)")
    client_name: Optional[str] = Field(None, description="Client name (single PO)")
    items: Optional[List[ImportItemData]] = Field(None, description="Items list (single PO)")
    
    # Multi-PO fields
    po_list: Optional[List[Dict]] = Field(None, description="List of POs with their items (multi-PO support)")
    total_pos: int = Field(0, description="Total number of POs found")
    
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


# ============================================================================
# FINANCE APPROVAL SCHEMAS
# ============================================================================

class FinanceDecision(str, Enum):
    """
    Decision type for the Finance Approval workflow.
    Used by POST /api/import/finance-decision.
    """
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class FinanceDecisionRequest(BaseModel):
    """
    Request body for the Finance Approval endpoint.

    Business rules enforced here (Pydantic layer):
      - item_id must be a valid UUID string
      - decision must be APPROVE or REJECT
      - justification must be at least 20 characters (prevents empty rubber-stamps)

    An AuditLog v2 entry is created server-side with:
      - to_status = "FINANCE_APPROVED" or "FINANCE_REJECTED"
      - extra_data = {"justification": <justification>, "decision": <decision>}
      - hash_version = 2 (includes tenant_id in SHA-256)
    """
    item_id: str = Field(
        ...,
        description="UUID of the staging item being reviewed"
    )
    decision: FinanceDecision = Field(
        ...,
        description="Finance decision: APPROVE or REJECT"
    )
    justification: str = Field(
        ...,
        min_length=20,
        max_length=2000,
        description="Written justification (min 20 chars, required for audit trail)"
    )

    @field_validator("item_id")
    @classmethod
    def validate_item_id_format(cls, v: str) -> str:
        """Ensure item_id is a valid UUID string to prevent injection."""
        import uuid as _uuid
        try:
            _uuid.UUID(v)
        except ValueError:
            raise ValueError(f"item_id must be a valid UUID, got: {v!r}")
        return v

    @field_validator("justification")
    @classmethod
    def validate_justification_not_whitespace(cls, v: str) -> str:
        """Ensure justification is not just whitespace."""
        stripped = v.strip()
        if len(stripped) < 20:
            raise ValueError(
                f"Justification must have at least 20 non-whitespace characters "
                f"(got {len(stripped)} after stripping)"
            )
        return stripped


class FinanceDecisionResponse(BaseModel):
    """
    Response from POST /api/import/finance-decision.
    Returns the audit log details for frontend confirmation.
    """
    success: bool = Field(..., description="Whether the decision was recorded")
    message: str = Field(..., description="Human-readable confirmation")
    item_id: str = Field(..., description="UUID of the item that was decided on")
    decision: FinanceDecision = Field(..., description="The decision that was recorded")
    new_status: str = Field(..., description="New item status after decision")
    audit_log_id: Optional[str] = Field(None, description="ID of the created AuditLog entry")
    audit_hash: Optional[str] = Field(None, description="SHA-256 hash of the audit entry (first 16 chars)")


class ConfirmStagingItemExtra(BaseModel):
    is_personalized: bool = False
    is_new_client: bool = False
    is_export: bool = False
    is_replacement: bool = False
    customization_notes: Optional[str] = None
    attachment_path: Optional[str] = None
    attachment_filename: Optional[str] = None
    apply_sla_reduction: bool = False
    finance_justification: Optional[str] = None


class ConfirmStagingItem(BaseModel):
    sku: str
    quantity: float
    price_unit: float
    unit_value: Optional[float] = None
    item_total_value: Optional[float] = None
    block_status: Optional[str] = None
    balance: Optional[float] = None
    delay: Optional[int] = None
    payment_terms: Optional[str] = None
    description: Optional[str] = None
    unit: Optional[str] = None
    width: Optional[float] = None
    length: Optional[float] = None
    lead_time: Optional[int] = None
    delivery_date: Optional[str] = None
    billing_date: Optional[str] = None
    order_date: Optional[str] = None          # Data do Pedido
    icms_percent: Optional[float] = None
    freight: Optional[float] = None
    salesperson: Optional[str] = None
    ipi: Optional[float] = None
    # NEW: ONET final production schema fields
    codigo_estruturado: Optional[str] = None  # Codigo Estruturado
    carrier_code: Optional[str] = None        # Cod. Transportadora
    carrier_name: Optional[str] = None        # Nome Transportadora
    extra_metadata: ConfirmStagingItemExtra


class ConfirmStagingPO(BaseModel):
    po_number: str
    client_name: str
    business_unit: str
    freight_cost: float = 0.0
    additional_costs: float = 0.0
    po_total_value: Optional[float] = None
    packaging_type: Optional[str] = None
    items: List[ConfirmStagingItem]

    @field_validator("business_unit")
    @classmethod
    def validate_business_unit(cls, v):
        allowed = ["Indústria", "Construção Civil", "Varejo", "Outros"]
        if v not in allowed:
            raise ValueError(f"Business unit must be one of: {', '.join(allowed)}")
        return v



class ConfirmStagingPayload(BaseModel):
    pos: List[ConfirmStagingPO]
    financial_override: bool = Field(
        default=False,
        description="If True, operator explicitly approved import despite financial mismatch. PO is routed to FINANCEIRO and an immutable audit log is created."
    )


