"""
FlexFlow - SLA Calculator
Utility functions for calculating SLA deadlines with configurable multipliers.
"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from backend.models import GlobalConfig
import uuid


def get_config_value(
    db: Session,
    tenant_id: uuid.UUID,
    config_key: str,
    default_value: float = 1.0
) -> float:
    """
    Get a configuration value from GlobalConfig.
    
    Args:
        db: Database session
        tenant_id: Tenant UUID
        config_key: Configuration key to retrieve
        default_value: Default value if config not found
        
    Returns:
        Configuration value as float
    """
    config = db.query(GlobalConfig).filter(
        GlobalConfig.tenant_id == tenant_id,
        GlobalConfig.config_key == config_key
    ).first()
    
    if config:
        return config.get_typed_value()
    
    return default_value


def calculate_sla_deadline(
    db: Session,
    tenant_id: uuid.UUID,
    base_days: int,
    is_replacement: bool = False,
    created_at: Optional[datetime] = None
) -> datetime:
    """
    Calculate SLA deadline with configurable multiplier for replacements.
    
    Args:
        db: Database session
        tenant_id: Tenant UUID
        base_days: Base number of days for SLA
        is_replacement: Whether this is a replacement order
        created_at: Order creation date (defaults to now)
        
    Returns:
        Calculated deadline datetime
    """
    if created_at is None:
        created_at = datetime.utcnow()
    
    # Get replacement multiplier from config
    multiplier = 1.0
    if is_replacement:
        multiplier = get_config_value(
            db=db,
            tenant_id=tenant_id,
            config_key="replacement_sla_multiplier",
            default_value=0.5
        )
    
    # Calculate adjusted days
    adjusted_days = base_days * multiplier
    
    # Calculate deadline
    deadline = created_at + timedelta(days=adjusted_days)
    
    return deadline


def get_sla_status(
    deadline: datetime,
    current_status: str,
    warning_days: int = 3,
    critical_days: int = 1
) -> dict:
    """
    Get SLA status information based on deadline.
    
    Args:
        deadline: SLA deadline datetime
        current_status: Current order status
        warning_days: Days before deadline to show warning
        critical_days: Days before deadline to show critical
        
    Returns:
        Dictionary with SLA status information
    """
    # If already completed, return green
    if current_status in ["COMPLETED", "CANCELLED"]:
        return {
            "status": "green",
            "severity": "ok",
            "message": "Pedido finalizado",
            "days_remaining": None
        }
    
    now = datetime.utcnow()
    days_remaining = (deadline - now).days
    
    # Determine status
    if days_remaining < 0:
        return {
            "status": "red",
            "severity": "overdue",
            "message": f"Atrasado há {abs(days_remaining)} dias",
            "days_remaining": days_remaining
        }
    elif days_remaining <= critical_days:
        return {
            "status": "red",
            "severity": "critical",
            "message": f"Crítico - {days_remaining} dia(s) restante(s)",
            "days_remaining": days_remaining
        }
    elif days_remaining <= warning_days:
        return {
            "status": "orange",
            "severity": "warning",
            "message": f"Atenção - {days_remaining} dia(s) restante(s)",
            "days_remaining": days_remaining
        }
    else:
        return {
            "status": "green",
            "severity": "ok",
            "message": f"{days_remaining} dia(s) restante(s)",
            "days_remaining": days_remaining
        }


def calculate_sla_with_metadata(
    db: Session,
    tenant_id: uuid.UUID,
    base_days: int,
    metadata: dict,
    created_at: Optional[datetime] = None
) -> dict:
    """
    Calculate SLA deadline and status using order metadata.
    
    Args:
        db: Database session
        tenant_id: Tenant UUID
        base_days: Base number of days for SLA
        metadata: Order metadata dictionary
        created_at: Order creation date
        
    Returns:
        Dictionary with deadline and status information
    """
    is_replacement = metadata.get("is_replacement", False)
    current_status = metadata.get("status", "DRAFT")
    
    deadline = calculate_sla_deadline(
        db=db,
        tenant_id=tenant_id,
        base_days=base_days,
        is_replacement=is_replacement,
        created_at=created_at
    )
    
    sla_status = get_sla_status(
        deadline=deadline,
        current_status=current_status
    )
    
    return {
        "deadline": deadline,
        "is_replacement": is_replacement,
        "multiplier_applied": 0.5 if is_replacement else 1.0,
        "base_days": base_days,
        "adjusted_days": base_days * (0.5 if is_replacement else 1.0),
        **sla_status
    }
