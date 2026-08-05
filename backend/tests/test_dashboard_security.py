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
