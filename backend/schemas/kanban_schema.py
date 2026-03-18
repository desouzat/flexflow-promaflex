"""
FlexFlow Kanban Schemas
Pydantic schemas for Kanban board operations.
"""

from typing import List, Optional
from decimal import Decimal
from datetime import datetime, date
from pydantic import BaseModel, Field


class POItemResponse(BaseModel):
    """Purchase Order Item response"""
    id: str = Field(..., description="Item ID")
    sku: str = Field(..., description="Product SKU")
    quantity: int = Field(..., description="Item quantity")
    price: Decimal = Field(..., description="Unit price")
    status_item: str = Field(..., description="Item status")
    margin_item: Optional[Decimal] = Field(None, description="Item margin")
    total_cost: Optional[Decimal] = Field(None, description="Total cost per unit")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class POResponse(BaseModel):
    """Purchase Order response"""
    id: str = Field(..., description="PO ID")
    po_number: str = Field(..., description="PO number")
    client_name: Optional[str] = Field(None, description="Client name")
    status_macro: str = Field(..., description="PO status")
    items: List[POItemResponse] = Field(default_factory=list, description="PO items")
    total_value: Optional[Decimal] = Field(None, description="Total PO value")
    margin_global: Optional[Decimal] = Field(None, description="Global margin")
    margin_percentage: Optional[Decimal] = Field(None, description="Margin percentage")
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


class MoveStatusResponse(BaseModel):
    """Response after moving status"""
    success: bool = Field(..., description="Whether transition succeeded")
    message: str = Field(..., description="Result message")
    po_id: str = Field(..., description="Purchase Order ID")
    from_status: str = Field(..., description="Previous status")
    to_status: str = Field(..., description="New status")
    validation_errors: Optional[List[str]] = Field(None, description="Validation errors if any")


class POFilterParams(BaseModel):
    """Filter parameters for PO list"""
    status: Optional[str] = Field(None, description="Filter by status")
    client_name: Optional[str] = Field(None, description="Filter by client name")
    po_number: Optional[str] = Field(None, description="Filter by PO number")
    created_after: Optional[date] = Field(None, description="Filter by creation date (after)")
    created_before: Optional[date] = Field(None, description="Filter by creation date (before)")
    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of records to return")
