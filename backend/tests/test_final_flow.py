import pytest
from fastapi.testclient import TestClient
import io
import uuid

from backend.main import app

client = TestClient(app)
TEST_PO_ID = "00000000-0000-0000-0000-000000000009"

@pytest.fixture(scope="module", autouse=True)
def setup_test_user_and_db():
    from backend.database import SessionLocal, engine, Base
    from backend.models import Tenant, User, PurchaseOrder, OrderItem
    from passlib.context import CryptContext

    # Create tables
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Check if tenant exists
        tenant = db.query(Tenant).filter(Tenant.cnpj == "12.345.678/0001-90").first()
        if not tenant:
            tenant = Tenant(
                id=uuid.uuid4(),
                name="PromaFlex",
                cnpj="12.345.678/0001-90",
                is_active=True
            )
            db.add(tenant)
            db.flush()

        # Check if user exists
        pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
        user = db.query(User).filter(User.email == "test@example.com").first()
        if not user:
            user = User(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                name="Test User",
                email="test@example.com",
                hashed_password=pwd_context.hash("password123"),
                role="admin",
                is_active=True
            )
            db.add(user)
            db.flush()

        # Seed test purchase order
        to_delete = db.query(PurchaseOrder).filter(PurchaseOrder.po_number.like("po-part-final-flow%")).all()
        for po in to_delete:
            db.query(OrderItem).filter(OrderItem.po_id == po.id).delete()
            db.delete(po)
        db.flush()

        po = PurchaseOrder(
            id=uuid.UUID(TEST_PO_ID),
            tenant_id=tenant.id,
            po_number="po-part-final-flow",
            status_macro="APPROVED",
            created_by=user.id,
            shipping_cost=300.0,
            po_total_value=2000.0
        )
        db.add(po)
        db.flush()

        # Seed OrderItems
        item1 = OrderItem(
            id=uuid.uuid4(),
            po_id=po.id,
            tenant_id=tenant.id,
            sku="SKU-PART-FF1",
            quantity=10,
            price=100.0,
            status_item="PENDING",
            unit_value=100.0,
            item_total_value=1000.0
        )
        item2 = OrderItem(
            id=uuid.uuid4(),
            po_id=po.id,
            tenant_id=tenant.id,
            sku="SKU-PART-FF2",
            quantity=10,
            price=100.0,
            status_item="PENDING",
            unit_value=100.0,
            item_total_value=1000.0
        )
        db.add(item1)
        db.add(item2)

        db.commit()
    finally:
        db.close()

@pytest.fixture
def auth_headers():
    response = client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_commercial_approval_to_shipping_and_freight_allocation(auth_headers):
    """
    Test final flow:
    1. Suggest a partition (which transitions PO to WAITING_COMMERCIAL_PARTITION)
    2. Move PO status to SHIPPING (Aprovar Partição from Commercial)
    3. Verify that the parent PO is archived and children POs are in SHIPPING status
    4. Allocate freight for the children POs (split sum can exceed/differ from parent)
    5. Verify children POs return to APPROVED (PCP) status
    """
    # 1. Suggest partition
    suggest_payload = {
        "po_id": TEST_PO_ID,
        "reason": "Test final flow partition suggestion justification of 10+ characters",
        "new_delivery_date": "2026-06-20T00:00:00Z",
        "qty_splits": {
            "SKU-PART-FF1": [5, 5],
            "SKU-PART-FF2": [5, 5]
        }
    }
    response_suggest = client.post(
        "/api/kanban/suggest-partition",
        headers=auth_headers,
        json=suggest_payload
    )
    assert response_suggest.status_code == 200

    # 2. Commercial Approval (move status to SHIPPING)
    response_move = client.post(
        "/api/kanban/move-status",
        headers=auth_headers,
        json={
            "po_id": TEST_PO_ID,
            "to_status": "SHIPPING"
        }
    )
    assert response_move.status_code == 200

    # 3. Check status is SHIPPING for children and get their IDs
    response_pos = client.get(
        "/api/kanban/pos",
        headers=auth_headers
    )
    assert response_pos.status_code == 200
    pos_list = response_pos.json()

    children = [po for po in pos_list if po.get("parent_po_id") == TEST_PO_ID]
    assert len(children) == 2

    for child in children:
        assert child["status_macro"] in ("SHIPPING", "Faturamento/Expedição")
        meta = child.get("partition_metadata") or {}
        assert meta.get("original_parent_freight") == 300.0
        assert meta.get("current_phase") == "FASE_A"

    # 4. Call Freight Allocation (using a sum that differs from parent to verify that validation is abolished)
    # Parent freight is 300.0, we allocate 200.0 + 200.0 = 400.0
    response_allocate = client.post(
        f"/api/kanban/pos/{children[0]['id']}/allocate-freight",
        headers=auth_headers,
        json={
            "freight_c1": 200.0,
            "freight_c2": 200.0
        }
    )
    assert response_allocate.status_code == 200

    # 5. Check status returns to APPROVED (PCP)
    for child in children:
        response_child = client.get(
            f"/api/kanban/pos/{child['id']}",
            headers=auth_headers
        )
        assert response_child.status_code == 200
        child_data = response_child.json()
        assert child_data["status_macro"] in ("APPROVED", "PCP")
        meta = child_data.get("partition_metadata") or {}
        assert meta.get("current_phase") == "FASE_B"
        assert meta.get("freight_allocated") is True
