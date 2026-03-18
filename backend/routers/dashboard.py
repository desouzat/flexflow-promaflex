"""
FlexFlow Dashboard Router
Endpoints for dashboard metrics and analytics.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from decimal import Decimal
from datetime import datetime, timedelta

from backend.schemas.dashboard_schema import (
    DashboardMetrics,
    MarginMetrics,
    LeadTimeMetrics,
    ItemsByAreaMetrics,
    AreaItemCount,
    DashboardSummary,
    StatusDistribution
)
from backend.schemas.auth_schema import UserInfo
from backend.database import get_db
from backend.routers.auth import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/metrics", response_model=DashboardMetrics)
async def get_dashboard_metrics(
    days: int = Query(30, ge=1, le=365, description="Number of days to include in metrics"),
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive dashboard metrics for the tenant.
    
    Returns:
    - **Margin Total**: Total margin across all POs
    - **Lead Time Médio**: Average lead time from creation to completion
    - **Contagem de Itens por Área**: Number of items in each status/area
    
    **Query Parameters:**
    - **days**: Number of days to include in calculations (default: 30)
    
    **Returns:**
    - Complete dashboard metrics
    """
    
    # In production, query database:
    # from sqlalchemy import func
    # pos = db.query(PurchaseOrder).filter(
    #     PurchaseOrder.tenant_id == current_user.tenant_id,
    #     PurchaseOrder.created_at >= datetime.utcnow() - timedelta(days=days)
    # ).all()
    
    # Mock data for demonstration
    
    # 1. Margin Metrics
    margin_metrics = MarginMetrics(
        total_margin=Decimal("45750.00"),  # Sum of all PO margins
        average_margin_percentage=Decimal("31.00"),  # Average margin %
        total_value=Decimal("150000.00"),  # Total value of all POs
        total_cost=Decimal("104250.00"),  # Total cost of all POs
        po_count=3  # Number of POs
    )
    
    # 2. Lead Time Metrics
    # Calculate average time from creation to completion
    lead_time_metrics = LeadTimeMetrics(
        average_lead_time_days=15.5,  # Average days to complete
        median_lead_time_days=14.0,  # Median days
        min_lead_time_days=10.0,  # Fastest completion
        max_lead_time_days=25.0,  # Slowest completion
        completed_po_count=5  # Number of completed POs
    )
    
    # 3. Items by Area/Status
    items_by_area = ItemsByAreaMetrics(
        total_items=225,
        by_area=[
            AreaItemCount(
                area="COMERCIAL",
                count=100,
                percentage=Decimal("44.44")
            ),
            AreaItemCount(
                area="PCP",
                count=50,
                percentage=Decimal("22.22")
            ),
            AreaItemCount(
                area="PRODUCAO",
                count=40,
                percentage=Decimal("17.78")
            ),
            AreaItemCount(
                area="EXPEDICAO_PENDENTE",
                count=15,
                percentage=Decimal("6.67")
            ),
            AreaItemCount(
                area="FATURAMENTO_PENDENTE",
                count=10,
                percentage=Decimal("4.44")
            ),
            AreaItemCount(
                area="DESPACHO",
                count=5,
                percentage=Decimal("2.22")
            ),
            AreaItemCount(
                area="CONCLUIDO",
                count=5,
                percentage=Decimal("2.22")
            )
        ]
    )
    
    return DashboardMetrics(
        margin=margin_metrics,
        lead_time=lead_time_metrics,
        items_by_area=items_by_area,
        tenant_id=current_user.tenant_id,
        generated_at=datetime.utcnow().isoformat()
    )


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get high-level dashboard summary.
    
    Provides quick overview metrics for the dashboard header.
    
    **Returns:**
    - Summary statistics and status distribution
    """
    
    # Mock data
    status_distribution = [
        StatusDistribution(
            status="COMERCIAL",
            count=5,
            percentage=Decimal("25.00")
        ),
        StatusDistribution(
            status="PCP",
            count=4,
            percentage=Decimal("20.00")
        ),
        StatusDistribution(
            status="PRODUCAO",
            count=3,
            percentage=Decimal("15.00")
        ),
        StatusDistribution(
            status="EXPEDICAO_PENDENTE",
            count=2,
            percentage=Decimal("10.00")
        ),
        StatusDistribution(
            status="FATURAMENTO_PENDENTE",
            count=2,
            percentage=Decimal("10.00")
        ),
        StatusDistribution(
            status="DESPACHO",
            count=2,
            percentage=Decimal("10.00")
        ),
        StatusDistribution(
            status="CONCLUIDO",
            count=2,
            percentage=Decimal("10.00")
        )
    ]
    
    return DashboardSummary(
        total_pos=20,
        total_items=225,
        active_pos=18,  # Not completed
        completed_pos=2,
        status_distribution=status_distribution,
        total_value=Decimal("500000.00"),
        total_margin=Decimal("150000.00")
    )


@router.get("/margin-trend")
async def get_margin_trend(
    days: int = Query(30, ge=7, le=365, description="Number of days for trend"),
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get margin trend over time.
    
    Returns daily margin data for charting.
    
    **Query Parameters:**
    - **days**: Number of days to include
    
    **Returns:**
    - Daily margin data points
    """
    
    # Mock trend data
    trend_data = []
    base_date = datetime.utcnow() - timedelta(days=days)
    
    for i in range(days):
        date = base_date + timedelta(days=i)
        # Simulate varying margins
        margin = 1000 + (i * 50) + ((i % 7) * 200)
        
        trend_data.append({
            "date": date.strftime("%Y-%m-%d"),
            "margin": margin,
            "po_count": 1 + (i % 3)
        })
    
    return {
        "trend": trend_data,
        "period_days": days,
        "total_margin": sum(d["margin"] for d in trend_data),
        "average_daily_margin": sum(d["margin"] for d in trend_data) / days
    }


@router.get("/lead-time-distribution")
async def get_lead_time_distribution(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get distribution of lead times.
    
    Shows how many POs fall into different lead time buckets.
    
    **Returns:**
    - Lead time distribution data
    """
    
    # Mock distribution data
    distribution = [
        {"range": "0-7 days", "count": 5, "percentage": 25.0},
        {"range": "8-14 days", "count": 8, "percentage": 40.0},
        {"range": "15-21 days", "count": 4, "percentage": 20.0},
        {"range": "22-30 days", "count": 2, "percentage": 10.0},
        {"range": "30+ days", "count": 1, "percentage": 5.0}
    ]
    
    return {
        "distribution": distribution,
        "total_pos": 20,
        "average_lead_time": 15.5
    }


@router.get("/top-clients")
async def get_top_clients(
    limit: int = Query(10, ge=1, le=50, description="Number of top clients to return"),
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get top clients by total value or margin.
    
    **Query Parameters:**
    - **limit**: Number of top clients to return
    
    **Returns:**
    - List of top clients with their metrics
    """
    
    # Mock client data
    clients = [
        {
            "client_name": "Acme Corp",
            "total_value": Decimal("150000.00"),
            "total_margin": Decimal("45000.00"),
            "margin_percentage": Decimal("30.00"),
            "po_count": 5,
            "avg_lead_time": 14.5
        },
        {
            "client_name": "Beta Industries",
            "total_value": Decimal("120000.00"),
            "total_margin": Decimal("36000.00"),
            "margin_percentage": Decimal("30.00"),
            "po_count": 4,
            "avg_lead_time": 16.0
        },
        {
            "client_name": "Gamma Solutions",
            "total_value": Decimal("100000.00"),
            "total_margin": Decimal("32000.00"),
            "margin_percentage": Decimal("32.00"),
            "po_count": 3,
            "avg_lead_time": 15.0
        },
        {
            "client_name": "Delta Corp",
            "total_value": Decimal("80000.00"),
            "total_margin": Decimal("24000.00"),
            "margin_percentage": Decimal("30.00"),
            "po_count": 3,
            "avg_lead_time": 17.0
        },
        {
            "client_name": "Epsilon Ltd",
            "total_value": Decimal("50000.00"),
            "total_margin": Decimal("15000.00"),
            "margin_percentage": Decimal("30.00"),
            "po_count": 2,
            "avg_lead_time": 13.0
        }
    ]
    
    return {
        "clients": clients[:limit],
        "total_clients": len(clients)
    }


@router.get("/status-timeline")
async def get_status_timeline(
    po_id: Optional[str] = Query(None, description="Specific PO ID to get timeline for"),
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get status transition timeline for a PO or average timeline.
    
    Shows how long POs spend in each status.
    
    **Query Parameters:**
    - **po_id**: Optional PO ID for specific timeline
    
    **Returns:**
    - Timeline data showing time spent in each status
    """
    
    if po_id:
        # Specific PO timeline
        timeline = [
            {
                "status": "COMERCIAL",
                "entered_at": "2024-03-01T10:00:00Z",
                "exited_at": "2024-03-03T14:30:00Z",
                "duration_hours": 52.5
            },
            {
                "status": "PCP",
                "entered_at": "2024-03-03T14:30:00Z",
                "exited_at": "2024-03-05T09:00:00Z",
                "duration_hours": 42.5
            },
            {
                "status": "PRODUCAO",
                "entered_at": "2024-03-05T09:00:00Z",
                "exited_at": "2024-03-15T17:00:00Z",
                "duration_hours": 248.0
            },
            {
                "status": "EXPEDICAO_PENDENTE",
                "entered_at": "2024-03-15T17:00:00Z",
                "exited_at": None,
                "duration_hours": None
            }
        ]
        
        return {
            "po_id": po_id,
            "timeline": timeline,
            "current_status": "EXPEDICAO_PENDENTE",
            "total_elapsed_hours": 343.0
        }
    else:
        # Average timeline across all POs
        avg_timeline = [
            {"status": "COMERCIAL", "avg_duration_hours": 48.0},
            {"status": "PCP", "avg_duration_hours": 36.0},
            {"status": "PRODUCAO", "avg_duration_hours": 240.0},
            {"status": "EXPEDICAO_PENDENTE", "avg_duration_hours": 24.0},
            {"status": "FATURAMENTO_PENDENTE", "avg_duration_hours": 24.0},
            {"status": "DESPACHO", "avg_duration_hours": 12.0}
        ]
        
        return {
            "type": "average",
            "timeline": avg_timeline,
            "total_avg_hours": sum(s["avg_duration_hours"] for s in avg_timeline),
            "po_count": 20
        }


@router.get("/alerts")
async def get_dashboard_alerts(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get dashboard alerts and notifications.
    
    Returns important alerts that need attention:
    - POs with approaching deadlines
    - POs stuck in a status too long
    - Low margin warnings
    - Missing attachments for personalized items
    
    **Returns:**
    - List of alerts with severity levels
    """
    
    alerts = [
        {
            "id": "alert-001",
            "severity": "high",
            "type": "deadline",
            "message": "PO-2024-001 delivery date is in 2 days",
            "po_id": "po-001",
            "po_number": "PO-2024-001",
            "created_at": "2024-03-15T10:00:00Z"
        },
        {
            "id": "alert-002",
            "severity": "medium",
            "type": "stuck",
            "message": "PO-2024-005 has been in PCP for 7 days",
            "po_id": "po-005",
            "po_number": "PO-2024-005",
            "created_at": "2024-03-14T15:30:00Z"
        },
        {
            "id": "alert-003",
            "severity": "low",
            "type": "margin",
            "message": "PO-2024-008 has margin below 20%",
            "po_id": "po-008",
            "po_number": "PO-2024-008",
            "created_at": "2024-03-13T09:00:00Z"
        },
        {
            "id": "alert-004",
            "severity": "high",
            "type": "attachment",
            "message": "PO-2024-003 has personalized items without attachments",
            "po_id": "po-003",
            "po_number": "PO-2024-003",
            "created_at": "2024-03-12T14:00:00Z"
        }
    ]
    
    return {
        "alerts": alerts,
        "total": len(alerts),
        "by_severity": {
            "high": 2,
            "medium": 1,
            "low": 1
        }
    }
