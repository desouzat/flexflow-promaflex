"""
Tests for SLA Calculator
Tests the configurable SLA multiplier logic for replacement orders.
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base
from backend.models import Tenant, GlobalConfig
from backend.utils.sla_calculator import (
    get_config_value,
    calculate_sla_deadline,
    get_sla_status,
    calculate_sla_with_metadata
)
import uuid


# Test database setup
@pytest.fixture
def db_session():
    """Create a test database session"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    # Create test tenant
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Test Tenant",
        cnpj="12.345.678/0001-90",
        is_active=True
    )
    session.add(tenant)
    
    # Create default config
    config = GlobalConfig(
        id=uuid.uuid4(),
        tenant_id=tenant.id,
        config_key="replacement_sla_multiplier",
        config_value="0.5",
        config_type="float",
        description="Test multiplier"
    )
    session.add(config)
    session.commit()
    
    yield session, tenant.id
    
    session.close()


def test_get_config_value(db_session):
    """Test retrieving config value from database"""
    session, tenant_id = db_session
    
    # Test existing config
    value = get_config_value(session, tenant_id, "replacement_sla_multiplier")
    assert value == 0.5
    
    # Test non-existing config with default
    value = get_config_value(session, tenant_id, "non_existing_key", default_value=1.0)
    assert value == 1.0


def test_calculate_sla_deadline_normal_order(db_session):
    """Test SLA calculation for normal orders (no multiplier)"""
    session, tenant_id = db_session
    
    base_days = 10
    created_at = datetime(2024, 1, 1, 12, 0, 0)
    
    deadline = calculate_sla_deadline(
        db=session,
        tenant_id=tenant_id,
        base_days=base_days,
        is_replacement=False,
        created_at=created_at
    )
    
    expected_deadline = created_at + timedelta(days=10)
    assert deadline == expected_deadline


def test_calculate_sla_deadline_replacement_order(db_session):
    """Test SLA calculation for replacement orders (with 0.5 multiplier)"""
    session, tenant_id = db_session
    
    base_days = 10
    created_at = datetime(2024, 1, 1, 12, 0, 0)
    
    deadline = calculate_sla_deadline(
        db=session,
        tenant_id=tenant_id,
        base_days=base_days,
        is_replacement=True,
        created_at=created_at
    )
    
    # With 0.5 multiplier, 10 days becomes 5 days
    expected_deadline = created_at + timedelta(days=5)
    assert deadline == expected_deadline


def test_get_sla_status_green():
    """Test SLA status when plenty of time remains"""
    deadline = datetime.utcnow() + timedelta(days=10)
    status = get_sla_status(deadline, "IN_PROGRESS")
    
    assert status["status"] == "green"
    assert status["severity"] == "ok"
    assert status["days_remaining"] > 3


def test_get_sla_status_warning():
    """Test SLA status when approaching deadline"""
    deadline = datetime.utcnow() + timedelta(days=2)
    status = get_sla_status(deadline, "IN_PROGRESS", warning_days=3)
    
    assert status["status"] == "orange"
    assert status["severity"] == "warning"
    assert status["days_remaining"] == 2


def test_get_sla_status_critical():
    """Test SLA status when very close to deadline"""
    deadline = datetime.utcnow() + timedelta(hours=12)
    status = get_sla_status(deadline, "IN_PROGRESS", critical_days=1)
    
    assert status["status"] == "red"
    assert status["severity"] == "critical"


def test_get_sla_status_overdue():
    """Test SLA status when past deadline"""
    deadline = datetime.utcnow() - timedelta(days=2)
    status = get_sla_status(deadline, "IN_PROGRESS")
    
    assert status["status"] == "red"
    assert status["severity"] == "overdue"
    assert status["days_remaining"] < 0


def test_get_sla_status_completed():
    """Test SLA status for completed orders"""
    deadline = datetime.utcnow() - timedelta(days=2)
    status = get_sla_status(deadline, "COMPLETED")
    
    assert status["status"] == "green"
    assert status["severity"] == "ok"


def test_calculate_sla_with_metadata_replacement(db_session):
    """Test full SLA calculation with replacement metadata"""
    session, tenant_id = db_session
    
    metadata = {
        "is_replacement": True,
        "status": "IN_PROGRESS"
    }
    
    created_at = datetime(2024, 1, 1, 12, 0, 0)
    
    result = calculate_sla_with_metadata(
        db=session,
        tenant_id=tenant_id,
        base_days=10,
        metadata=metadata,
        created_at=created_at
    )
    
    assert result["is_replacement"] is True
    assert result["multiplier_applied"] == 0.5
    assert result["base_days"] == 10
    assert result["adjusted_days"] == 5.0
    assert "deadline" in result
    assert "status" in result


def test_calculate_sla_with_metadata_normal(db_session):
    """Test full SLA calculation with normal order metadata"""
    session, tenant_id = db_session
    
    metadata = {
        "is_replacement": False,
        "status": "IN_PROGRESS"
    }
    
    created_at = datetime(2024, 1, 1, 12, 0, 0)
    
    result = calculate_sla_with_metadata(
        db=session,
        tenant_id=tenant_id,
        base_days=10,
        metadata=metadata,
        created_at=created_at
    )
    
    assert result["is_replacement"] is False
    assert result["multiplier_applied"] == 1.0
    assert result["base_days"] == 10
    assert result["adjusted_days"] == 10.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
