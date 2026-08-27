import pytest
import json
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

def test_celso_kpis_fix():
    app.dependency_overrides[get_db] = override_get_db
    try:
        # Create a valid admin JWT token
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
        
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Forwarded-For": "127.0.0.1",
            "X-Real-IP": "127.0.0.1"
        }
        
        response = client.get("/api/dashboard/celso-kpis", headers=headers)
        
        print("\n" + "="*80)
        print("MANDATORY END-TO-END TEST OUTPUT FOR CELSO KPIS FIX")
        print("="*80)
        print(f"HTTP Status Code: {response.status_code}")
        print("JSON Response:")
        print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        print("="*80)

        # Assert HTTP 200 OK
        assert response.status_code == 200, f"Expected HTTP 200 OK, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "portfolio_by_unit" in data, "Response payload missing 'portfolio_by_unit'"
        assert "Site" in data["portfolio_by_unit"], "'portfolio_by_unit' missing key 'Site'"
    finally:
        app.dependency_overrides.clear()
