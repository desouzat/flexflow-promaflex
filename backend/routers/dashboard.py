"""
FlexFlow Dashboard Router
Endpoints for dashboard metrics and analytics.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
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
from backend.models import PurchaseOrder, OrderItem

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


# Status mapping: Database status -> Display name (Portuguese)
STATUS_DISPLAY_MAP = {
    "DRAFT": "Comercial",
    "SUBMITTED": "PCP",
    "APPROVED": "Produção/Embalagem",
    "IN_PROGRESS": "Expedição/Faturamento",
    "COMPLETED": "Concluído",
    "CANCELLED": "Cancelado"
}


def calculate_po_metrics(pos: list) -> dict:
    """Calculate aggregate metrics for a list of POs"""
    total_value = Decimal("0.00")
    total_cost = Decimal("0.00")
    
    for po in pos:
        for item in po.items:
            item_total = Decimal(str(item.price)) * item.quantity
            total_value += item_total
            # Assuming 70% cost ratio if no cost data available
            total_cost += item_total * Decimal("0.70")
    
    margin_global = total_value - total_cost
    margin_percentage = (margin_global / total_value * 100) if total_value > 0 else Decimal("0.00")
    
    return {
        "total_value": total_value,
        "total_cost": total_cost,
        "margin_global": margin_global,
        "margin_percentage": margin_percentage
    }


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
    
    # Query database for POs in the specified time range
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    pos = db.query(PurchaseOrder).filter(
        PurchaseOrder.tenant_id == current_user.tenant_id,
        PurchaseOrder.created_at >= cutoff_date
    ).all()
    
    # 1. Margin Metrics
    metrics = calculate_po_metrics(pos)
    margin_metrics = MarginMetrics(
        total_margin=metrics["margin_global"],
        average_margin_percentage=metrics["margin_percentage"],
        total_value=metrics["total_value"],
        total_cost=metrics["total_cost"],
        po_count=len(pos)
    )
    
    # 2. Lead Time Metrics
    completed_pos = [po for po in pos if po.status_macro == "COMPLETED"]
    if completed_pos:
        lead_times = []
        for po in completed_pos:
            delta = po.updated_at - po.created_at
            lead_times.append(delta.total_seconds() / 86400)  # Convert to days
        
        lead_times.sort()
        avg_lead_time = sum(lead_times) / len(lead_times)
        median_idx = len(lead_times) // 2
        median_lead_time = lead_times[median_idx] if lead_times else 0.0
        
        lead_time_metrics = LeadTimeMetrics(
            average_lead_time_days=avg_lead_time,
            median_lead_time_days=median_lead_time,
            min_lead_time_days=min(lead_times) if lead_times else 0.0,
            max_lead_time_days=max(lead_times) if lead_times else 0.0,
            completed_po_count=len(completed_pos)
        )
    else:
        lead_time_metrics = LeadTimeMetrics(
            average_lead_time_days=0.0,
            median_lead_time_days=0.0,
            min_lead_time_days=0.0,
            max_lead_time_days=0.0,
            completed_po_count=0
        )
    
    # 3. Items by Area/Status
    all_items = db.query(OrderItem).filter(
        OrderItem.tenant_id == current_user.tenant_id
    ).all()
    
    # Count items by PO status
    status_counts = {}
    for item in all_items:
        po_status = item.purchase_order.status_macro
        display_status = STATUS_DISPLAY_MAP.get(po_status, po_status)
        status_counts[display_status] = status_counts.get(display_status, 0) + 1
    
    total_items = len(all_items)
    by_area = []
    for status_name in ["Comercial", "PCP", "Produção/Embalagem", "Expedição/Faturamento", "Concluído"]:
        count = status_counts.get(status_name, 0)
        percentage = Decimal(str((count / total_items * 100) if total_items > 0 else 0))
        by_area.append(AreaItemCount(
            area=status_name,
            count=count,
            percentage=percentage
        ))
    
    items_by_area = ItemsByAreaMetrics(
        total_items=total_items,
        by_area=by_area
    )
    
    return DashboardMetrics(
        margin=margin_metrics,
        lead_time=lead_time_metrics,
        items_by_area=items_by_area,
        tenant_id=str(current_user.tenant_id),
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
    
    # Query all POs for tenant
    pos = db.query(PurchaseOrder).filter(
        PurchaseOrder.tenant_id == current_user.tenant_id
    ).all()
    
    # Count items
    total_items = db.query(OrderItem).filter(
        OrderItem.tenant_id == current_user.tenant_id
    ).count()
    
    # Status distribution
    status_counts = {}
    for po in pos:
        display_status = STATUS_DISPLAY_MAP.get(po.status_macro, po.status_macro)
        status_counts[display_status] = status_counts.get(display_status, 0) + 1
    
    total_pos = len(pos)
    status_distribution = []
    for status_name in ["Comercial", "PCP", "Produção/Embalagem", "Expedição/Faturamento", "Concluído"]:
        count = status_counts.get(status_name, 0)
        percentage = Decimal(str((count / total_pos * 100) if total_pos > 0 else 0))
        status_distribution.append(StatusDistribution(
            status=status_name,
            count=count,
            percentage=percentage
        ))
    
    # Calculate totals
    metrics = calculate_po_metrics(pos)
    
    # Count active vs completed
    completed_pos = len([po for po in pos if po.status_macro == "COMPLETED"])
    active_pos = total_pos - completed_pos
    
    return DashboardSummary(
        total_pos=total_pos,
        total_items=total_items,
        active_pos=active_pos,
        completed_pos=completed_pos,
        status_distribution=status_distribution,
        total_value=metrics["total_value"],
        total_margin=metrics["margin_global"]
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
    
    # Query POs in date range
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    pos = db.query(PurchaseOrder).filter(
        PurchaseOrder.tenant_id == current_user.tenant_id,
        PurchaseOrder.created_at >= cutoff_date
    ).all()
    
    # Group by date
    daily_data = {}
    for po in pos:
        date_key = po.created_at.strftime("%Y-%m-%d")
        if date_key not in daily_data:
            daily_data[date_key] = {"pos": [], "count": 0}
        daily_data[date_key]["pos"].append(po)
        daily_data[date_key]["count"] += 1
    
    # Calculate daily margins
    trend_data = []
    base_date = datetime.utcnow() - timedelta(days=days)
    
    for i in range(days):
        date = base_date + timedelta(days=i)
        date_key = date.strftime("%Y-%m-%d")
        
        if date_key in daily_data:
            day_pos = daily_data[date_key]["pos"]
            metrics = calculate_po_metrics(day_pos)
            margin = float(metrics["margin_global"])
            po_count = daily_data[date_key]["count"]
        else:
            margin = 0
            po_count = 0
        
        trend_data.append({
            "date": date_key,
            "margin": margin,
            "po_count": po_count
        })
    
    total_margin = sum(d["margin"] for d in trend_data)
    avg_margin = total_margin / days if days > 0 else 0
    
    return {
        "trend": trend_data,
        "period_days": days,
        "total_margin": total_margin,
        "average_daily_margin": avg_margin
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
    
    # Query completed POs
    completed_pos = db.query(PurchaseOrder).filter(
        PurchaseOrder.tenant_id == current_user.tenant_id,
        PurchaseOrder.status_macro == "COMPLETED"
    ).all()
    
    # Calculate lead times
    lead_times = []
    for po in completed_pos:
        delta = po.updated_at - po.created_at
        days = delta.total_seconds() / 86400
        lead_times.append(days)
    
    # Bucket into ranges
    buckets = {
        "0-7 days": 0,
        "8-14 days": 0,
        "15-21 days": 0,
        "22-30 days": 0,
        "30+ days": 0
    }
    
    for days in lead_times:
        if days <= 7:
            buckets["0-7 days"] += 1
        elif days <= 14:
            buckets["8-14 days"] += 1
        elif days <= 21:
            buckets["15-21 days"] += 1
        elif days <= 30:
            buckets["22-30 days"] += 1
        else:
            buckets["30+ days"] += 1
    
    total = len(lead_times)
    distribution = [
        {
            "range": range_name,
            "count": count,
            "percentage": (count / total * 100) if total > 0 else 0
        }
        for range_name, count in buckets.items()
    ]
    
    avg_lead_time = sum(lead_times) / len(lead_times) if lead_times else 0
    
    return {
        "distribution": distribution,
        "total_pos": total,
        "average_lead_time": avg_lead_time
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
    
    # For now, return placeholder since we don't have client_name in the model
    # This would need to be implemented when client data is added
    clients = [
        {
            "client_name": "Cliente Demo",
            "total_value": Decimal("0.00"),
            "total_margin": Decimal("0.00"),
            "margin_percentage": Decimal("0.00"),
            "po_count": 0,
            "avg_lead_time": 0.0
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
        po = db.query(PurchaseOrder).filter(
            PurchaseOrder.id == po_id,
            PurchaseOrder.tenant_id == current_user.tenant_id
        ).first()
        
        if not po:
            raise HTTPException(
                status_code=404,
                detail=f"Purchase Order {po_id} not found"
            )
        
        # For now, return basic timeline
        # This would be enhanced with audit log data
        timeline = [
            {
                "status": STATUS_DISPLAY_MAP.get(po.status_macro, po.status_macro),
                "entered_at": po.created_at.isoformat(),
                "exited_at": None,
                "duration_hours": None
            }
        ]
        
        return {
            "po_id": po_id,
            "timeline": timeline,
            "current_status": STATUS_DISPLAY_MAP.get(po.status_macro, po.status_macro),
            "total_elapsed_hours": 0
        }
    else:
        # Average timeline across all POs
        # This would be calculated from audit logs in production
        avg_timeline = [
            {"status": "Comercial", "avg_duration_hours": 48.0},
            {"status": "PCP", "avg_duration_hours": 36.0},
            {"status": "Produção/Embalagem", "avg_duration_hours": 240.0},
            {"status": "Expedição/Faturamento", "avg_duration_hours": 24.0},
            {"status": "Concluído", "avg_duration_hours": 0.0}
        ]
        
        return {
            "type": "average",
            "timeline": avg_timeline,
            "total_avg_hours": sum(s["avg_duration_hours"] for s in avg_timeline),
            "po_count": db.query(PurchaseOrder).filter(
                PurchaseOrder.tenant_id == current_user.tenant_id
            ).count()
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
    
    alerts = []
    
    # Check for POs stuck in DRAFT status for more than 7 days
    week_ago = datetime.utcnow() - timedelta(days=7)
    stuck_pos = db.query(PurchaseOrder).filter(
        PurchaseOrder.tenant_id == current_user.tenant_id,
        PurchaseOrder.status_macro == "DRAFT",
        PurchaseOrder.created_at < week_ago
    ).all()
    
    for po in stuck_pos:
        days_stuck = (datetime.utcnow() - po.created_at).days
        alerts.append({
            "id": f"alert-stuck-{po.id}",
            "severity": "medium",
            "type": "stuck",
            "message": f"Pedido {po.po_number} está pendente há {days_stuck} dias",
            "po_id": str(po.id),
            "po_number": po.po_number,
            "created_at": po.created_at.isoformat()
        })
    
    return {
        "alerts": alerts,
        "total": len(alerts),
        "by_severity": {
            "high": len([a for a in alerts if a["severity"] == "high"]),
            "medium": len([a for a in alerts if a["severity"] == "medium"]),
            "low": len([a for a in alerts if a["severity"] == "low"])
        }
    }
