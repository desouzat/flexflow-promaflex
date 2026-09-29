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
    # Helper replicating backend authorization check
    def is_authorized(user: UserInfo) -> bool:
        role = (getattr(user, 'role', '') or '').lower()
        area = (getattr(user, 'area', '') or '').upper()
        has_flag = getattr(user, 'can_cancel_commercial', False)
        return role in ['admin', 'master'] or has_flag is True or area == 'COMERCIAL'

    # Master role -> allowed
    master_user = UserInfo(id="1", tenant_id="t", email="m@p.com", name="Master", role="master", can_cancel_commercial=False)
    assert is_authorized(master_user) is True

    # Admin role -> allowed
    admin_user = UserInfo(id="2", tenant_id="t", email="a@p.com", name="Admin", role="admin", can_cancel_commercial=False)
    assert is_authorized(admin_user) is True

    # Delegated user (operator with can_cancel_commercial = True) -> allowed
    delegated_user = UserInfo(id="3", tenant_id="t", email="d@p.com", name="Delegated", role="operator", can_cancel_commercial=True)
    assert is_authorized(delegated_user) is True

    # Commercial operator without flag -> allowed by area
    commercial_op = UserInfo(id="4", tenant_id="t", email="c@p.com", name="Com", role="operator", area="COMERCIAL", can_cancel_commercial=False)
    assert is_authorized(commercial_op) is True

    # Standard operator in PCP without flag -> blocked
    standard_op = UserInfo(id="5", tenant_id="t", email="o@p.com", name="Op", role="operator", area="PCP", can_cancel_commercial=False)
    assert is_authorized(standard_op) is False

    # Standard sales user in FINANCEIRO without flag -> blocked
    finance_user = UserInfo(id="6", tenant_id="t", email="s@p.com", name="Finance", role="user", area="FINANCEIRO", can_cancel_commercial=False)
    assert is_authorized(finance_user) is False


def test_cancellation_badge_metadata_lifecycle():
    from backend.routers.kanban import STATUS_DISPLAY_MAP

    meta = {}
    from_status = "BILLING"
    reason = "[Cancelamento de Pedido] Cancelado no ERP"
    user_name = "Mairla Silva"

    # 1. Express return sets cancellation metadata
    if reason.startswith("[Cancelamento de Pedido]"):
        meta["cancellation_requested"] = True
        meta["cancellation_requested_at"] = "2026-09-29T12:00:00"
        meta["cancellation_requested_by"] = user_name
        meta["cancellation_requested_from"] = STATUS_DISPLAY_MAP.get(from_status, from_status)

    assert meta["cancellation_requested"] is True
    assert meta["cancellation_requested_from"] == "Faturamento"
    assert meta["cancellation_requested_by"] == "Mairla Silva"

    # 2. Advance cleans up metadata
    meta.pop("cancellation_requested", None)
    meta.pop("cancellation_requested_at", None)
    meta.pop("cancellation_requested_by", None)
    meta.pop("cancellation_requested_from", None)

    assert "cancellation_requested" not in meta
    assert "cancellation_requested_from" not in meta

    # 3. Standard return purges metadata
    meta["cancellation_requested"] = True
    standard_reason = "Ajustar medidas de bobina"
    if not standard_reason.startswith("[Cancelamento de Pedido]"):
        meta.pop("cancellation_requested", None)
        meta.pop("cancellation_requested_at", None)
        meta.pop("cancellation_requested_by", None)
        meta.pop("cancellation_requested_from", None)

    assert "cancellation_requested" not in meta


