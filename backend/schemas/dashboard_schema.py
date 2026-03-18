"""
FlexFlow Dashboard Schemas
Pydantic schemas for dashboard metrics and analytics.
"""

from typing import List, Dict, Optional
from decimal import Decimal
from pydantic import BaseModel, Field


class MarginMetrics(BaseModel):
    """Margin metrics for dashboard"""
    total_margin: Decimal = Field(..., description="Total margin across all POs")
    average_margin_percentage: Decimal = Field(..., description="Average margin percentage")
    total_value: Decimal = Field(..., description="Total value of all POs")
    total_cost: Decimal = Field(..., description="Total cost of all POs")
    po_count: int = Field(..., description="Number of POs included in calculation")


class LeadTimeMetrics(BaseModel):
    """Lead time metrics for dashboard"""
    average_lead_time_days: Optional[float] = Field(None, description="Average lead time in days")
    median_lead_time_days: Optional[float] = Field(None, description="Median lead time in days")
    min_lead_time_days: Optional[float] = Field(None, description="Minimum lead time in days")
    max_lead_time_days: Optional[float] = Field(None, description="Maximum lead time in days")
    completed_po_count: int = Field(..., description="Number of completed POs")


class AreaItemCount(BaseModel):
    """Item count by area/status"""
    area: str = Field(..., description="Area or status name")
    count: int = Field(..., description="Number of items in this area")
    percentage: Decimal = Field(..., description="Percentage of total items")


class ItemsByAreaMetrics(BaseModel):
    """Items distribution by area"""
    total_items: int = Field(..., description="Total number of items")
    by_area: List[AreaItemCount] = Field(..., description="Items grouped by area/status")


class DashboardMetrics(BaseModel):
    """Complete dashboard metrics"""
    margin: MarginMetrics = Field(..., description="Margin metrics")
    lead_time: LeadTimeMetrics = Field(..., description="Lead time metrics")
    items_by_area: ItemsByAreaMetrics = Field(..., description="Items by area metrics")
    tenant_id: str = Field(..., description="Tenant ID")
    generated_at: str = Field(..., description="Metrics generation timestamp")


class StatusDistribution(BaseModel):
    """Distribution of POs by status"""
    status: str = Field(..., description="Status name")
    count: int = Field(..., description="Number of POs")
    percentage: Decimal = Field(..., description="Percentage of total")


class DashboardSummary(BaseModel):
    """Summary dashboard data"""
    total_pos: int = Field(..., description="Total number of POs")
    total_items: int = Field(..., description="Total number of items")
    active_pos: int = Field(..., description="Number of active POs")
    completed_pos: int = Field(..., description="Number of completed POs")
    status_distribution: List[StatusDistribution] = Field(..., description="POs by status")
    total_value: Decimal = Field(..., description="Total value of all POs")
    total_margin: Decimal = Field(..., description="Total margin")
