import sys
import os

# Add project root directory to path to import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from fastapi.testclient import TestClient
import uuid

from backend.main import app

client = TestClient(app)
TEST_PO_ID = "00000000-0000-0000-0000-000000000099"

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
            db.commit()
            db.refresh(tenant)

        # Clear existing test user and test POs to avoid key conflicts
        db.query(User).filter(User.email == "test_partition@example.com").delete()
        db.commit()

        # Check if user exists
        pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
        user = User(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            name="Test User",
            email="test_partition@example.com",
            hashed_password=pwd_context.hash("password123"),
            role="admin",
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Seed test purchase order
        to_delete = db.query(PurchaseOrder).filter(PurchaseOrder.po_number.like("po-fix-partition%")).all()
        for po in to_delete:
            db.query(OrderItem).filter(OrderItem.po_id == po.id).delete()
            db.delete(po)
        db.commit()

        po = PurchaseOrder(
            id=uuid.UUID(TEST_PO_ID),
            tenant_id=tenant.id,
            po_number="po-fix-partition",
            status_macro="APPROVED",
            created_by=user.id,
            shipping_cost=300.0,
            po_total_value=2000.0
        )
        db.add(po)
        db.commit()
        db.refresh(po)

        # Seed OrderItems
        item1 = OrderItem(
            id=uuid.uuid4(),
            po_id=po.id,
            tenant_id=tenant.id,
            sku="SKU-PART-FIX1",
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
            sku="SKU-PART-FIX2",
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
            "email": "test_partition@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_suggest_partition_endpoint(auth_headers):
    """
    Test the suggest_partition endpoint to ensure no ForeignKeyViolation occurs
    and Child POs and OrderItems are properly flushed and committed.
    """
    suggest_payload = {
        "po_id": TEST_PO_ID,
        "reason": "Test partition suggestion justification of 10+ characters",
        "new_delivery_date": "2026-06-20T00:00:00Z",
        "qty_splits": {
            "SKU-PART-FIX1": [5, 5],
            "SKU-PART-FIX2": [5, 5]
        }
    }
    response_suggest = client.post(
        "/api/kanban/suggest-partition",
        headers=auth_headers,
        json=suggest_payload
    )
    assert response_suggest.status_code == 200
    assert response_suggest.json()["success"] is True
    assert "child1_id" in response_suggest.json()
    assert "child2_id" in response_suggest.json()
