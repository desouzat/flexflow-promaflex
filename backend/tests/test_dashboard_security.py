import pytest
from fastapi import HTTPException, status
from backend.routers.dashboard import require_admin_or_master_role
from backend.schemas.auth_schema import UserInfo

def test_dashboard_access_admin_allowed():
    user = UserInfo(
        id="user-admin",
        email="admin@promaflex.com.br",
        role="admin",
        tenant_id="tenant-1",
        name="Admin User"
    )
    result = require_admin_or_master_role(current_user=user)
    assert result.role == "admin"

def test_dashboard_access_master_allowed():
    user = UserInfo(
        id="user-master",
        email="master@promaflex.com.br",
        role="master",
        tenant_id="tenant-1",
        name="Master User"
    )
    result = require_admin_or_master_role(current_user=user)
    assert result.role == "master"

def test_dashboard_access_operator_blocked():
    user = UserInfo(
        id="user-op",
        email="comercial@promaflex.com.br",
        role="operator",
        tenant_id="tenant-1",
        name="Operator User"
    )
    with pytest.raises(HTTPException) as exc_info:
        require_admin_or_master_role(current_user=user)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Acesso negado" in exc_info.value.detail

def test_dashboard_access_user_blocked():
    user = UserInfo(
        id="user-sales",
        email="alexandre@promaflex.com.br",
        role="user",
        tenant_id="tenant-1",
        name="Salesperson User"
    )
    with pytest.raises(HTTPException) as exc_info:
        require_admin_or_master_role(current_user=user)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Acesso negado" in exc_info.value.detail


def test_dashboard_vp_factor_type_safety():
    from decimal import Decimal
    from backend.routers.kanban import parse_payment_terms_to_days
    
    payment_terms_str = "28/35/42 DDL"
    payment_days = parse_payment_terms_to_days(payment_terms_str)
    
    vp_factor_float = pow(1.025, float(payment_days) / 30.0)
    vp_factor = Decimal(str(round(vp_factor_float, 6)))
    
    item_total = Decimal("6359.04")
    # Division between Decimal and Decimal must succeed without raising TypeError
    item_vp = item_total / vp_factor
    assert isinstance(item_vp, Decimal)
    assert item_vp < item_total

