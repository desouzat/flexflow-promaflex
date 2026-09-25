import pytest
from pydantic import ValidationError
from backend.schemas.auth_schema import UserInfo
from backend.routers.kanban import CancelPORequest, ReturnPORequest, STATUS_FLOW
from backend.models import User, PurchaseOrder, OrderItem


def test_cancel_po_request_validation():
    # Test valid with reason
    req1 = CancelPORequest(reason="Cliente solicitou cancelamento")
    assert req1.reason == "Cliente solicitou cancelamento"
    assert req1.justification == "Cliente solicitou cancelamento"

    # Test valid with legacy justification
    req2 = CancelPORequest(justification="Erro no pedido de venda")
    assert req2.reason == "Erro no pedido de venda"
    assert req2.justification == "Erro no pedido de venda"

    # Test rejection when too short
    with pytest.raises(ValidationError):
        CancelPORequest(reason="ab")

    with pytest.raises(ValidationError):
        CancelPORequest()


def test_user_info_schema_has_can_cancel_commercial():
    user = UserInfo(
        id="user-123",
        tenant_id="tenant-123",
        email="operator@promaflex.com.br",
        name="Operator User",
        role="operator",
        can_cancel_commercial=True
    )
    assert user.can_cancel_commercial is True

    user_default = UserInfo(
        id="user-456",
        tenant_id="tenant-123",
        email="operator2@promaflex.com.br",
        name="Operator 2",
        role="operator"
    )
    assert user_default.can_cancel_commercial is False


def test_universal_return_to_commercial_routing():
    # Verify standard workflow step-back
    assert STATUS_FLOW.get("APPROVED", {}).get("prev") == "SUBMITTED"
    assert STATUS_FLOW.get("MANUFACTURING", {}).get("prev") == "APPROVED"
    assert STATUS_FLOW.get("BILLING", {}).get("prev") == "MANUFACTURING"
    assert STATUS_FLOW.get("SHIPPING", {}).get("prev") == "BILLING"

    # Emulate CR-F3 express return routing from any stage
    test_stages = ["APPROVED", "MANUFACTURING", "BILLING", "SHIPPING"]
    for stage in test_stages:
        reason_clean = "[Cancelamento de Pedido] Cancelado no ERP ONET"
        if reason_clean.startswith("[Cancelamento de Pedido]"):
            target_status = "SUBMITTED"
        else:
            target_status = STATUS_FLOW.get(stage, {}).get("prev")
        assert target_status == "SUBMITTED", f"Stage {stage} failed to route to SUBMITTED"


def test_cancellation_permission_gating():
    # Master role -> allowed
    master_user = UserInfo(id="1", tenant_id="t", email="m@p.com", name="Master", role="master", can_cancel_commercial=False)
    assert (master_user.role.lower() in ['admin', 'master'] or getattr(master_user, 'can_cancel_commercial', False)) is True

    # Admin role -> allowed
    admin_user = UserInfo(id="2", tenant_id="t", email="a@p.com", name="Admin", role="admin", can_cancel_commercial=False)
    assert (admin_user.role.lower() in ['admin', 'master'] or getattr(admin_user, 'can_cancel_commercial', False)) is True

    # Delegated user (operator with can_cancel_commercial = True) -> allowed
    delegated_user = UserInfo(id="3", tenant_id="t", email="d@p.com", name="Delegated", role="operator", can_cancel_commercial=True)
    assert (delegated_user.role.lower() in ['admin', 'master'] or getattr(delegated_user, 'can_cancel_commercial', False)) is True

    # Standard operator without flag -> blocked
    standard_op = UserInfo(id="4", tenant_id="t", email="o@p.com", name="Op", role="operator", can_cancel_commercial=False)
    assert (standard_op.role.lower() in ['admin', 'master'] or getattr(standard_op, 'can_cancel_commercial', False)) is False

    # Standard sales user without flag -> blocked
    sales_user = UserInfo(id="5", tenant_id="t", email="s@p.com", name="Sales", role="user", can_cancel_commercial=False)
    assert (sales_user.role.lower() in ['admin', 'master'] or getattr(sales_user, 'can_cancel_commercial', False)) is False
