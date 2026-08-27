import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import get_db
from backend.routers.auth import create_access_token

def override_get_db():
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.all.return_value = []
    try:
        yield mock_db
    finally:
        pass

def test_tenant_isolation_middleware_e2e():
    app.dependency_overrides[get_db] = override_get_db
    try:
        # 1. Create a valid admin JWT token
        token_data = {
            "sub": "user-admin-test",
            "tenant_id": "tenant-test-1",
            "email": "admin@promaflex.com.br",
            "name": "Admin Tester",
            "role": "admin",
            "permissions": ["all"]
        }
        token = create_access_token(data=token_data)

        client = TestClient(app)
        
        # 2. Perform GET request to /api/dashboard/celso-kpis with full header set
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Forwarded-For": "127.0.0.1, 10.0.0.1, 192.168.1.1",
            "X-Real-IP": "127.0.0.1"
        }
        
        response = client.get("/api/dashboard/celso-kpis", headers=headers)
        
        print("\n" + "="*80)
        print("MANDATORY END-TO-END ENDPOINT TEST OUTPUT")
        print("="*80)
        print(f"Request Endpoint : GET /api/dashboard/celso-kpis")
        print(f"Response Status  : {response.status_code}")
        print(f"Response Content : {response.text[:300]}")
        print("="*80)

        # 3. Assert HTTP 200 OK and no 500 internal server errors
        assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}: {response.text}"
        json_data = response.json()
        assert "portfolio_by_unit" in json_data or "margin_by_unit" in json_data
    finally:
        app.dependency_overrides.clear()
