import pytest
from fastapi import HTTPException, status
from backend.routers.import_router import require_staging_access
from backend.schemas.auth_schema import UserInfo

def test_staging_access_official_commercial_allowed():
    user = UserInfo(
        id="user-1",
        email="comercial@promaflex.com.br",
        role="operator",
        tenant_id="tenant-1",
        name="Comercial Official"
    )
    result = require_staging_access(current_user=user)
    assert result.email == "comercial@promaflex.com.br"

def test_staging_access_admin_allowed():
    user = UserInfo(
        id="user-admin",
        email="admin@promaflex.com.br",
        role="admin",
        tenant_id="tenant-1",
        name="Admin User"
    )
    result = require_staging_access(current_user=user)
    assert result.role == "admin"

def test_staging_access_master_allowed():
    user = UserInfo(
        id="user-master",
        email="master@promaflex.com.br",
        role="master",
        tenant_id="tenant-1",
        name="Master User"
    )
    result = require_staging_access(current_user=user)
    assert result.role == "master"

def test_staging_access_individual_salesperson_blocked():
    user = UserInfo(
        id="user-alexandre",
        email="alexandre@promaflex.com.br",
        role="user",
        tenant_id="tenant-1",
        name="Alexandre Salesperson"
    )
    with pytest.raises(HTTPException) as exc_info:
        require_staging_access(current_user=user)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Acesso negado" in exc_info.value.detail

def test_staging_access_other_operator_blocked():
    user = UserInfo(
        id="user-other-op",
        email="vendedor2@promaflex.com.br",
        role="operator",
        tenant_id="tenant-1",
        name="Other Operator"
    )
    with pytest.raises(HTTPException) as exc_info:
        require_staging_access(current_user=user)
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Acesso negado" in exc_info.value.detail
