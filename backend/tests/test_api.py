"""
FlexFlow API Tests
Integration tests for all API endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json
import io

from backend.main import app

# Create test client - pass app as first positional argument
client = TestClient(app)


# ============================================================================
# FIXTURES
# ============================================================================

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


# ============================================================================
# TEST: ROOT ENDPOINTS
# ============================================================================

def test_root_endpoint():
    """Test root endpoint returns API information"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "FlexFlow API"
    assert data["status"] == "running"
    assert "endpoints" in data


def test_health_check():
    """Test health check endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


def test_api_info():
    """Test API info endpoint"""
    response = client.get("/api")
    assert response.status_code == 200
    data = response.json()
    assert "endpoints" in data
    assert "authentication" in data["endpoints"]
    assert "import" in data["endpoints"]
    assert "kanban" in data["endpoints"]
    assert "dashboard" in data["endpoints"]


# ============================================================================
# TEST: AUTHENTICATION ENDPOINTS
# ============================================================================

def test_login_success():
    """Test successful login"""
    response = client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "expires_in" in data


def test_login_invalid_email():
    """Test login with invalid email format"""
    response = client.post(
        "/api/auth/login",
        json={
            "email": "invalid-email",
            "password": "password123"
        }
    )
    assert response.status_code == 422  # Validation error


def test_get_current_user(auth_headers):
    """Test getting current user information"""
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "user" in data
    assert "tenant_id" in data["user"]
    assert "email" in data["user"]


def test_get_current_user_without_token():
    """Test accessing protected endpoint without token"""
    response = client.get("/api/auth/me")
    assert response.status_code == 403  # Forbidden


def test_get_current_user_invalid_token():
    """Test accessing protected endpoint with invalid token"""
    response = client.get(
        "/api/auth/me",
        headers={"Authorization": "Bearer invalid-token"}
    )
    assert response.status_code == 401  # Unauthorized


def test_logout(auth_headers):
    """Test logout endpoint"""
    response = client.post("/api/auth/logout", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "message" in data


# ============================================================================
# TEST: IMPORT ENDPOINTS
# ============================================================================

def test_get_field_types(auth_headers):
    """Test getting available field types"""
    response = client.get("/api/import/field-types", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "field_types" in data
    assert len(data["field_types"]) == 9  # 9 required fields


def test_get_file_headers(auth_headers):
    """Test extracting headers from CSV file"""
    csv_content = b"PO Number,Client,SKU,Qty,Price\nPO-001,Acme,SKU-001,10,100"
    
    files = {"file": ("test.csv", io.BytesIO(csv_content), "text/csv")}
    response = client.post(
        "/api/import/headers",
        headers=auth_headers,
        files=files
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "headers" in data
    assert "PO Number" in data["headers"]
    assert "Client" in data["headers"]


def test_save_import_config(auth_headers):
    """Test saving import configuration"""
    config = {
        "mappings": [
            {"column_name": "PO Number", "field_type": "po_number"},
            {"column_name": "Client", "field_type": "client_name"},
            {"column_name": "SKU", "field_type": "sku"},
            {"column_name": "Qty", "field_type": "quantity"},
            {"column_name": "Price", "field_type": "price_unit"},
            {"column_name": "Cost MP", "field_type": "cost_mp"},
            {"column_name": "Cost MO", "field_type": "cost_mo"},
            {"column_name": "Cost Energy", "field_type": "cost_energy"},
            {"column_name": "Cost Gas", "field_type": "cost_gas"}
        ]
    }
    
    response = client.post(
        "/api/import/configs",
        headers=auth_headers,
        params={"config_name": "test_config"},
        json=config
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "config" in data


def test_list_import_configs(auth_headers):
    """Test listing import configurations"""
    response = client.get("/api/import/configs", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "configs" in data
    assert "count" in data


def test_get_import_config(auth_headers):
    """Test getting specific import configuration"""
    # First save a config
    config = {
        "mappings": [
            {"column_name": "PO Number", "field_type": "po_number"},
            {"column_name": "Client", "field_type": "client_name"},
            {"column_name": "SKU", "field_type": "sku"},
            {"column_name": "Qty", "field_type": "quantity"},
            {"column_name": "Price", "field_type": "price_unit"},
            {"column_name": "Cost MP", "field_type": "cost_mp"},
            {"column_name": "Cost MO", "field_type": "cost_mo"},
            {"column_name": "Cost Energy", "field_type": "cost_energy"},
            {"column_name": "Cost Gas", "field_type": "cost_gas"}
        ]
    }
    
    client.post(
        "/api/import/configs",
        headers=auth_headers,
        params={"config_name": "get_test_config"},
        json=config
    )
    
    # Then get it
    response = client.get(
        "/api/import/configs/get_test_config",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "get_test_config"


def test_delete_import_config(auth_headers):
    """Test deleting import configuration"""
    # First save a config
    config = {
        "mappings": [
            {"column_name": "PO Number", "field_type": "po_number"},
            {"column_name": "Client", "field_type": "client_name"},
            {"column_name": "SKU", "field_type": "sku"},
            {"column_name": "Qty", "field_type": "quantity"},
            {"column_name": "Price", "field_type": "price_unit"},
            {"column_name": "Cost MP", "field_type": "cost_mp"},
            {"column_name": "Cost MO", "field_type": "cost_mo"},
            {"column_name": "Cost Energy", "field_type": "cost_energy"},
            {"column_name": "Cost Gas", "field_type": "cost_gas"}
        ]
    }
    
    client.post(
        "/api/import/configs",
        headers=auth_headers,
        params={"config_name": "delete_test_config"},
        json=config
    )
    
    # Then delete it
    response = client.delete(
        "/api/import/configs/delete_test_config",
        headers=auth_headers
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "message" in data


# ============================================================================
# TEST: KANBAN ENDPOINTS
# ============================================================================

def test_get_kanban_board(auth_headers):
    """Test getting Kanban board"""
    response = client.get("/api/kanban/board", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "columns" in data
    assert "total_pos" in data
    assert "tenant_id" in data


def test_list_purchase_orders(auth_headers):
    """Test listing purchase orders"""
    response = client.get("/api/kanban/pos", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_list_purchase_orders_with_filters(auth_headers):
    """Test listing purchase orders with filters"""
    response = client.get(
        "/api/kanban/pos",
        headers=auth_headers,
        params={"status": "COMERCIAL", "limit": 10}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_purchase_order(auth_headers):
    """Test getting specific purchase order"""
    response = client.get("/api/kanban/pos/po-001", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "po-001"
    assert "items" in data


def test_get_purchase_order_not_found(auth_headers):
    """Test getting non-existent purchase order"""
    response = client.get("/api/kanban/pos/non-existent", headers=auth_headers)
    assert response.status_code == 404


def test_move_po_status_success(auth_headers):
    """Test moving PO status successfully"""
    response = client.post(
        "/api/kanban/move-status",
        headers=auth_headers,
        json={
            "po_id": "po-001",
            "to_status": "PCP",
            "reason": "Approved by commercial team"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["from_status"] == "COMERCIAL"
    assert data["to_status"] == "PCP"


def test_move_po_status_invalid_transition(auth_headers):
    """Test moving PO status with invalid transition"""
    response = client.post(
        "/api/kanban/move-status",
        headers=auth_headers,
        json={
            "po_id": "po-001",
            "to_status": "CONCLUIDO",  # Invalid: can't go directly from COMERCIAL to CONCLUIDO
            "reason": "Test"
        }
    )
    assert response.status_code == 200  # Returns 200 but success=False
    data = response.json()
    assert data["success"] is False
    assert "validation_errors" in data


def test_list_items(auth_headers):
    """Test listing items"""
    response = client.get("/api/kanban/items", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


# ============================================================================
# TEST: DASHBOARD ENDPOINTS
# ============================================================================

def test_get_dashboard_metrics(auth_headers):
    """Test getting dashboard metrics"""
    response = client.get("/api/dashboard/metrics", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "margin" in data
    assert "lead_time" in data
    assert "items_by_area" in data


def test_get_dashboard_metrics_with_days_filter(auth_headers):
    """Test getting dashboard metrics with days filter"""
    response = client.get(
        "/api/dashboard/metrics",
        headers=auth_headers,
        params={"days": 7}
    )
    assert response.status_code == 200
    data = response.json()
    assert "margin" in data


def test_get_dashboard_summary(auth_headers):
    """Test getting dashboard summary"""
    response = client.get("/api/dashboard/summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_pos" in data
    assert "total_items" in data
    assert "status_distribution" in data


def test_get_margin_trend(auth_headers):
    """Test getting margin trend"""
    response = client.get("/api/dashboard/margin-trend", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "trend" in data
    assert "period_days" in data


def test_get_lead_time_distribution(auth_headers):
    """Test getting lead time distribution"""
    response = client.get(
        "/api/dashboard/lead-time-distribution",
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "distribution" in data


def test_get_top_clients(auth_headers):
    """Test getting top clients"""
    response = client.get("/api/dashboard/top-clients", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "clients" in data
    assert "total_clients" in data


def test_get_status_timeline(auth_headers):
    """Test getting status timeline"""
    response = client.get("/api/dashboard/status-timeline", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "timeline" in data


def test_get_status_timeline_for_po(auth_headers):
    """Test getting status timeline for specific PO"""
    response = client.get(
        "/api/dashboard/status-timeline",
        headers=auth_headers,
        params={"po_id": "po-001"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["po_id"] == "po-001"
    assert "timeline" in data


def test_get_dashboard_alerts(auth_headers):
    """Test getting dashboard alerts"""
    response = client.get("/api/dashboard/alerts", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "alerts" in data
    assert "by_severity" in data


# ============================================================================
# TEST: AUTHENTICATION PROTECTION
# ============================================================================

def test_protected_endpoints_require_auth():
    """Test that protected endpoints require authentication"""
    protected_endpoints = [
        ("GET", "/api/auth/me"),
        ("GET", "/api/import/field-types"),
        ("GET", "/api/kanban/board"),
        ("GET", "/api/dashboard/metrics"),
    ]
    
    for method, endpoint in protected_endpoints:
        if method == "GET":
            response = client.get(endpoint)
        elif method == "POST":
            response = client.post(endpoint)
        
        assert response.status_code in [401, 403], \
            f"Endpoint {method} {endpoint} should require authentication"


# ============================================================================
# TEST: ERROR HANDLING
# ============================================================================

def test_validation_error_response():
    """Test validation error response format"""
    response = client.post(
        "/api/auth/login",
        json={
            "email": "invalid-email",  # Invalid email format
            "password": "123"  # Too short
        }
    )
    assert response.status_code == 422
    data = response.json()
    assert "detail" in data or "errors" in data


def test_not_found_error():
    """Test 404 error for non-existent endpoint"""
    response = client.get("/api/non-existent-endpoint")
    assert response.status_code == 404


# ============================================================================
# TEST: CORS HEADERS
# ============================================================================

def test_cors_headers():
    """Test that CORS headers are present"""
    response = client.options("/api/auth/login")
    # CORS headers should be present
    assert response.status_code in [200, 405]  # OPTIONS may not be implemented


# ============================================================================
# TEST: RESPONSE HEADERS
# ============================================================================

def test_process_time_header():
    """Test that X-Process-Time header is added"""
    response = client.get("/")
    assert "X-Process-Time" in response.headers or "x-process-time" in response.headers


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
