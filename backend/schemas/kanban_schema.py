"""
FlexFlow Kanban Schemas
Pydantic schemas for Kanban board operations.
"""

from typing import List, Optional, Any
from decimal import Decimal
from datetime import datetime, date
from pydantic import BaseModel, Field, validator


class POItemResponse(BaseModel):
    """Purchase Order Item response"""
    id: str = Field(..., description="Item ID")
    sku: str = Field(..., description="Product SKU")
    quantity: int = Field(..., description="Item quantity")
    price: Decimal = Field(..., description="Unit price")
    status_item: str = Field(..., description="Item status")
    margin_item: Optional[Any] = Field(None, description="Item margin")
    total_cost: Optional[Decimal] = Field(None, description="Total cost per unit")
    item_total_value: Optional[Decimal] = Field(None, description="Item total value (Total Item)")
    manual_commission_rate: Optional[Decimal] = Field(None, description="Manual commission rate override (MASTER only)")
    extra_metadata: Optional[dict] = Field(None, description="Extra metadata for item")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class POResponse(BaseModel):
    """Purchase Order response"""
    id: str = Field(..., description="PO ID")
    po_number: str = Field(..., description="PO number")
    client_name: Optional[str] = Field(None, description="Client name")
    supplier_name: Optional[str] = Field(None, description="Supplier name (alias for client_name)")
    status_macro: str = Field(..., description="PO status")
    status: str = Field(..., description="PO status (alias for status_macro)")
    items: List[POItemResponse] = Field(default_factory=list, description="PO items")
    items_count: int = Field(0, description="Number of items in PO")
    total_value: Optional[Decimal] = Field(None, description="Total PO value")
    margin_global: Optional[Any] = Field(None, description="Global margin")
    margin_percentage: Optional[Any] = Field(None, description="Margin percentage")
    commission_rate: Optional[Decimal] = Field(None, description="Commission rate percentage")
    commission_value: Optional[Decimal] = Field(None, description="Commission value in currency")
    shipping_cost: Optional[Decimal] = Field(None, description="Shipping cost")
    expected_delivery_date: Optional[datetime] = Field(None, description="Expected delivery date")
    delivery_date: Optional[datetime] = Field(None, description="Original delivery date (Excel)")
    data_limite: Optional[datetime] = Field(None, description="Data Limite de Entrega (delivery_date - 2 days)")
    priority: Optional[str] = Field("normal", description="Priority level (normal, high)")
    extra_metadata: Optional[dict] = Field(None, description="Extra metadata for PO")
    partition_metadata: Optional[dict] = Field(None, description="Partition metadata for PO (alias)")
    logistics_checklist: Optional[dict] = Field(None, description="Logistics checklist data")
    partition_reason: Optional[str] = Field(None, description="Partition justification/reason")
    parent_po_id: Optional[str] = Field(None, description="Parent PO ID if partitioned")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    created_by: Optional[str] = Field(None, description="Creator user ID")


class KanbanColumn(BaseModel):
    """Kanban column with POs"""
    status: str = Field(..., description="Status/Column name")
    count: int = Field(..., description="Number of POs in this status")
    pos: List[POResponse] = Field(default_factory=list, description="Purchase Orders")


class KanbanBoardResponse(BaseModel):
    """Complete Kanban board response"""
    columns: List[KanbanColumn] = Field(..., description="Kanban columns")
    total_pos: int = Field(..., description="Total number of POs")
    tenant_id: str = Field(..., description="Tenant ID")


class MoveStatusRequest(BaseModel):
    """Request to move PO to new status"""
    po_id: str = Field(..., description="Purchase Order ID")
    to_status: str = Field(..., description="Target status")
    reason: Optional[str] = Field(None, description="Reason for status change")
    metadata: Optional[dict] = Field(None, description="Additional metadata")
    skip_validation: bool = Field(
        default=False,
        description="Permitir salto de etapa (apenas LEADER/MASTER)"
    )
    justificativa_lider: Optional[str] = Field(
        None,
        description="Justificativa obrigatória para salto de etapa"
    )

    @validator('justificativa_lider')
    def validate_justification(cls, v, values):
        """Validar que justificativa é obrigatória quando skip_validation=True"""
        if values.get('skip_validation') and not v:
            raise ValueError('Justificativa é obrigatória para salto de etapa')
        if values.get('skip_validation') and v and len(v.strip()) < 10:
            raise ValueError('Justificativa deve ter pelo menos 10 caracteres')
        return v


class MoveStatusResponse(BaseModel):
    """Response after moving status"""
    success: bool = Field(..., description="Whether transition succeeded")
    message: str = Field(..., description="Result message")
    po_id: str = Field(..., description="Purchase Order ID")
    from_status: str = Field(..., description="Previous status")
    to_status: str = Field(..., description="New status")
    validation_errors: Optional[List[str]] = Field(None, description="Validation errors if any")
    is_exception: bool = Field(default=False, description="Se foi um salto de etapa excepcional")


class POFilterParams(BaseModel):
    """Filter parameters for PO list"""
    status: Optional[str] = Field(None, description="Filter by status")
    client_name: Optional[str] = Field(None, description="Filter by client name")
    po_number: Optional[str] = Field(None, description="Filter by PO number")
    created_after: Optional[date] = Field(None, description="Filter by creation date (after)")
    created_before: Optional[date] = Field(None, description="Filter by creation date (before)")
    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of records to return")


class UpdateCommissionRequest(BaseModel):
    """Request to update manual commission rate"""
    po_id: str = Field(..., description="Purchase Order ID")
    item_id: Optional[str] = Field(None, description="Item ID (if updating specific item)")
    manual_commission_rate: Decimal = Field(..., description="Manual commission rate percentage", ge=0, le=100)
    justification: str = Field(..., description="Justification for manual override", min_length=10)


class UpdateCommissionResponse(BaseModel):
    """Response after updating commission"""
    success: bool = Field(..., description="Whether update succeeded")
    message: str = Field(..., description="Result message")
    po_id: str = Field(..., description="Purchase Order ID")
    new_commission_rate: Decimal = Field(..., description="New commission rate")
    new_margin: Decimal = Field(..., description="Recalculated margin")
    updated_by: str = Field(..., description="User who made the update")


class UpdateLogisticsChecklistRequest(BaseModel):
    """Request to update logistics checklist"""
    po_id: str = Field(..., description="Purchase Order ID")
    endereco_conferido: bool = Field(False, description="Endereço Conferido")
    peso_validado: bool = Field(False, description="Peso Validado")
    etiquetas_impressas: bool = Field(False, description="Etiquetas Impressas")
    foto_carga_path: Optional[str] = Field(None, description="Path to Foto da Carga")
    foto_canhoto_path: Optional[str] = Field(None, description="Path to Foto do Canhoto/NF")


class UpdateLogisticsChecklistResponse(BaseModel):
    """Response after updating logistics checklist"""
    success: bool = Field(..., description="Whether update succeeded")
    message: str = Field(..., description="Result message")
    po_id: str = Field(..., description="Purchase Order ID")
    checklist_complete: bool = Field(..., description="Whether all checklist items are complete")
    can_dispatch: bool = Field(..., description="Whether dispatch can be completed")
