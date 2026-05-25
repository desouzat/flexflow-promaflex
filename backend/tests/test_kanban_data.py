import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import PurchaseOrder, AuditLog
import json

client = TestClient(app)

@pytest.fixture
def auth_token():
    """Get a valid authentication token"""
    response = client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    return response.json()["access_token"]

@pytest.fixture
def auth_headers(auth_token):
    """Get authentication headers"""
    return {"Authorization": f"Bearer {auth_token}"}

def test_kanban_handoff_history(auth_headers):
    """
    Assert that the handoff-history endpoint successfully retrieves transitions
    and handoff_history is NOT empty for seeded POs.
    """
    db = SessionLocal()
    try:
        # Find PO-CLEAN-002 or PO-CLEAN-001
        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == "PO-CLEAN-002").first()
        if not po:
            # Fallback to any PO
            po = db.query(PurchaseOrder).first()
            
        assert po is not None, "At least one seeded PurchaseOrder must exist"
        
        # Verify that there are audit logs for this PO
        # Logs are joined via OrderItem
        from backend.models import OrderItem
        logs = db.query(AuditLog).join(OrderItem).filter(OrderItem.po_id == po.id).all()
        assert len(logs) > 0, f"There must be at least one transition logged in audit_logs for PO {po.po_number}"
        
        # Make request to the endpoint
        response = client.get(f"/api/kanban/pos/{po.id}/handoff-history", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get handoff-history: {response.text}"
        
        data = response.json()
        print("\n=== KANBAN HANDOFF HISTORY API RESPONSE ===")
        print(json.dumps(data, indent=2))
        
        assert "handoff_history" in data, "Response must contain 'handoff_history' key"
        assert isinstance(data["handoff_history"], list), "'handoff_history' must be a list"
        assert len(data["handoff_history"]) > 0, "'handoff_history' list must NOT be empty"
        print(f"Success! handoff_history contains {len(data['handoff_history'])} transition steps.")
        print("===========================================\n")
        
    finally:
        db.close()
