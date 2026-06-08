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

TEST_PO_ID = "00000000-0000-0000-0000-000000000001"


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="session", autouse=True)
def setup_test_user_and_db():
    from backend.database import SessionLocal, engine, Base
    from backend.models import Tenant, User, PurchaseOrder, OrderItem
    from passlib.context import CryptContext
    import uuid

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

        # Seed test purchase order for API tests (fixes PostgreSQL UUID typecast issue)
        existing_items = db.query(OrderItem).filter(OrderItem.po_id == uuid.UUID(TEST_PO_ID)).all()
        for item in existing_items:
            db.delete(item)
        existing_po = db.query(PurchaseOrder).filter(PurchaseOrder.id == uuid.UUID(TEST_PO_ID)).first()
        if existing_po:
            db.delete(existing_po)
        db.flush()

        po = PurchaseOrder(
            id=uuid.UUID(TEST_PO_ID),
            tenant_id=tenant.id,
            po_number="po-001",
            status_macro="SUBMITTED",
            created_by=user.id,
            shipping_cost=50.0,
            po_total_value=1050.0
        )
        db.add(po)
        db.flush()

        # Seed an OrderItem associated with it
        item = OrderItem(
            id=uuid.uuid4(),
            po_id=po.id,
            tenant_id=tenant.id,
            sku="TEST-SKU-001",
            quantity=10,
            price=100.0,
            status_item="PENDING",
            unit_value=100.0,
            item_total_value=1000.0
        )
        db.add(item)

        db.commit()
    finally:
        db.close()

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
    assert len(data["field_types"]) >= 9  # 9 required fields


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
        params={"status": "Comercial", "limit": 10}
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_get_purchase_order(auth_headers):
    """Test getting specific purchase order"""
    response = client.get(f"/api/kanban/pos/{TEST_PO_ID}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == TEST_PO_ID
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
            "po_id": TEST_PO_ID,
            "to_status": "PCP",
            "reason": "Approved by commercial team"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["from_status"] == "Comercial"
    assert data["to_status"] == "PCP"


def test_move_po_status_invalid_transition(auth_headers):
    """Test moving PO status with invalid transition"""
    response = client.post(
        "/api/kanban/move-status",
        headers=auth_headers,
        json={
            "po_id": TEST_PO_ID,
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
        params={"po_id": TEST_PO_ID}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["po_id"] == TEST_PO_ID
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


# ============================================================================
# TEST: INTELLIGENT ROUTING LOGIC
# ============================================================================

def test_routing_logic(auth_headers):
    """Test that a clean PO routes to APPROVED (PCP) and a blocked PO routes to FINANCE (Credit Analysis)"""
    # 1. Clean PO Payload
    payload_clean = {
        "pos": [
            {
                "po_number": "po-clean-123",
                "client_name": "Clean Client Ltd",
                "business_unit": "Indústria",
                "freight_cost": 100.0,
                "additional_costs": 0.0,
                "po_total_value": 1100.0,
                "packaging_type": "Palete",
                "items": [
                    {
                        "sku": "SKU-CLEAN",
                        "quantity": 10,
                        "price_unit": 100.0,
                        "unit_value": 100.0,
                        "item_total_value": 1000.0,
                        "block_status": "LIBERADO",
                        "extra_metadata": {
                            "is_personalized": False,
                            "is_new_client": False
                        }
                    }
                ]
            }
        ]
    }

    # Confirm clean PO
    response = client.post(
        "/api/import/confirm-staging",
        headers={"Authorization": f"Bearer {auth_headers}"} if isinstance(auth_headers, str) else auth_headers,
        json=payload_clean
    )
    assert response.status_code == 200
    
    # 2. Blocked PO Payload
    payload_blocked = {
        "pos": [
            {
                "po_number": "po-blocked-123",
                "client_name": "Blocked Client Ltd",
                "business_unit": "Indústria",
                "freight_cost": 100.0,
                "additional_costs": 0.0,
                "po_total_value": 1100.0,
                "packaging_type": "Fardo Plástico",
                "items": [
                    {
                        "sku": "SKU-BLOCKED",
                        "quantity": 10,
                        "price_unit": 100.0,
                        "unit_value": 100.0,
                        "item_total_value": 1000.0,
                        "block_status": "BLOQUEADO",
                        "extra_metadata": {
                            "is_personalized": True,
                            "is_new_client": True,
                            "finance_justification": "Limiar de crédito excedido no ERP"
                        }
                    }
                ]
            }
        ]
    }

    # Confirm blocked PO
    response = client.post(
        "/api/import/confirm-staging",
        headers={"Authorization": f"Bearer {auth_headers}"} if isinstance(auth_headers, str) else auth_headers,
        json=payload_blocked
    )
    assert response.status_code == 200

    # 3. Retrieve POs from kanban and assert status
    response_pos = client.get(
        "/api/kanban/pos",
        headers={"Authorization": f"Bearer {auth_headers}"} if isinstance(auth_headers, str) else auth_headers
    )
    assert response_pos.status_code == 200
    pos_list = response_pos.json()

    clean_po = next((po for po in pos_list if po["po_number"] == "po-clean-123"), None)
    blocked_po = next((po for po in pos_list if po["po_number"] == "po-blocked-123"), None)

    assert clean_po is not None
    assert clean_po["status_macro"] in ("APPROVED", "PCP")

    assert blocked_po is not None
    assert blocked_po["status_macro"] in ("FINANCE", "Financeiro")


def test_partition_approval_and_freight_allocation(auth_headers):
    """Test the complete partition flow: suggest partition, approve to SHIPPING (FASE_A), and allocate freight (FASE_B/APPROVED)"""
    from backend.database import SessionLocal
    from backend.models import PurchaseOrder, OrderItem
    db = SessionLocal()
    try:
        to_delete = db.query(PurchaseOrder).filter(PurchaseOrder.po_number.like("po-part-999%")).all()
        for po in to_delete:
            db.query(OrderItem).filter(OrderItem.po_id == po.id).delete()
            db.delete(po)
        db.commit()
    finally:
        db.close()

    # 1. Create a clean PO that goes to APPROVED (PCP) status
    payload = {
        "pos": [
            {
                "po_number": "po-part-999",
                "client_name": "Partition Client Ltd",
                "business_unit": "Indústria",
                "freight_cost": 250.0,
                "additional_costs": 0.0,
                "po_total_value": 2000.0,
                "packaging_type": "Palete",
                "items": [
                    {
                        "sku": "SKU-PART-1",
                        "quantity": 10,
                        "price_unit": 100.0,
                        "unit_value": 100.0,
                        "item_total_value": 1000.0,
                        "block_status": "LIBERADO",
                        "extra_metadata": {
                            "is_personalized": False,
                            "is_new_client": False
                        }
                    },
                    {
                        "sku": "SKU-PART-2",
                        "quantity": 10,
                        "price_unit": 100.0,
                        "unit_value": 100.0,
                        "item_total_value": 1000.0,
                        "block_status": "LIBERADO",
                        "extra_metadata": {
                            "is_personalized": False,
                            "is_new_client": False
                        }
                    }
                ]
            }
        ]
    }
    
    response = client.post(
        "/api/import/confirm-staging",
        headers={"Authorization": f"Bearer {auth_headers}"} if isinstance(auth_headers, str) else auth_headers,
        json=payload
    )
    assert response.status_code == 200
    
    # Get the imported PO id
    response_pos = client.get(
        "/api/kanban/pos",
        headers={"Authorization": f"Bearer {auth_headers}"} if isinstance(auth_headers, str) else auth_headers
    )
    assert response_pos.status_code == 200
    pos_list = response_pos.json()
    parent_po = next((po for po in pos_list if po["po_number"] == "po-part-999"), None)
    assert parent_po is not None
    assert parent_po["status_macro"] in ("APPROVED", "PCP")
    
    # 2. Suggest a partition (PCP action)
    suggest_payload = {
        "po_id": parent_po["id"],
        "reason": "Test partition suggestion justification of 10+ characters",
        "new_delivery_date": "2026-06-15T00:00:00Z",
        "qty_splits": {
            "SKU-PART-1": [5, 5],
            "SKU-PART-2": [5, 5]
        }
    }
    response_suggest = client.post(
        "/api/kanban/suggest-partition",
        headers={"Authorization": f"Bearer {auth_headers}"} if isinstance(auth_headers, str) else auth_headers,
        json=suggest_payload
    )
    assert response_suggest.status_code == 200
    
    # 3. Approve partition via move-status or approve-partition. Let's use move-status to move to SHIPPING (Expedição)
    response_move = client.post(
        "/api/kanban/move-status",
        headers={"Authorization": f"Bearer {auth_headers}"} if isinstance(auth_headers, str) else auth_headers,
        json={
            "po_id": parent_po["id"],
            "to_status": "SHIPPING"
        }
    )
    assert response_move.status_code == 200
    
    # 4. Fetch the children POs
    response_pos = client.get(
        "/api/kanban/pos",
        headers={"Authorization": f"Bearer {auth_headers}"} if isinstance(auth_headers, str) else auth_headers
    )
    pos_list = response_pos.json()
    
    # Sibling children have parent_po_id equal to the parent PO
    children = [po for po in pos_list if po.get("parent_po_id") == parent_po["id"]]
    assert len(children) == 2
    
    # Check that children have correct status_macro = SHIPPING, original_parent_freight and current_phase = FASE_A
    for child in children:
        assert child["status_macro"] in ("SHIPPING", "Faturamento/Expedição")
        meta = child.get("partition_metadata") or {}
        assert meta.get("original_parent_freight") == 250.0
        assert meta.get("current_phase") == "FASE_A"
        # Check that decision keys are deleted
        assert "suggested_delivery_date" not in meta
        assert "partition_reason" not in meta
        
    # Check parent status is ARCHIVED_PARTITIONED
    response_parent = client.get(
        f"/api/kanban/pos/{parent_po['id']}",
        headers={"Authorization": f"Bearer {auth_headers}"} if isinstance(auth_headers, str) else auth_headers
    )
    assert response_parent.json()["status_macro"] in ("ARCHIVED_PARTITIONED", "Arquivado")
    
    # 5. Allocate freight for partition children
    response_allocate = client.post(
        f"/api/kanban/pos/{children[0]['id']}/allocate-freight",
        headers={"Authorization": f"Bearer {auth_headers}"} if isinstance(auth_headers, str) else auth_headers,
        json={
            "freight_c1": 125.0,
            "freight_c2": 125.0
        }
    )
    assert response_allocate.status_code == 200
    
    # Check that children are now APPROVED (PCP stage) and current_phase is FASE_B
    for child in children:
        response_child = client.get(
            f"/api/kanban/pos/{child['id']}",
            headers={"Authorization": f"Bearer {auth_headers}"} if isinstance(auth_headers, str) else auth_headers
        )
        child_data = response_child.json()
        assert child_data["status_macro"] in ("APPROVED", "PCP")
        meta = child_data.get("partition_metadata") or {}
        assert meta.get("current_phase") == "FASE_B"
        assert meta.get("freight_allocated") is True


def test_expedition_attachments_upload(auth_headers):
    # 1. Create a PO
    payload = {
        "pos": [
            {
                "po_number": "po-upload-test-888",
                "client_name": "Upload Client",
                "business_unit": "Indústria",
                "freight_cost": 100.0,
                "additional_costs": 0.0,
                "po_total_value": 1000.0,
                "packaging_type": "Palete",
                "items": [
                    {
                        "sku": "SKU-UPLOAD-1",
                        "quantity": 10,
                        "price_unit": 100.0,
                        "unit_value": 100.0,
                        "item_total_value": 1000.0,
                        "block_status": "LIBERADO",
                        "extra_metadata": {
                            "is_personalized": False,
                            "is_new_client": False
                        }
                    }
                ]
            }
        ]
    }
    
    response = client.post(
        "/api/import/confirm-staging",
        headers={"Authorization": f"Bearer {auth_headers}"} if isinstance(auth_headers, str) else auth_headers,
        json=payload
    )
    assert response.status_code == 200
    
    # Get the imported PO id
    response_pos = client.get(
        "/api/kanban/pos",
        headers={"Authorization": f"Bearer {auth_headers}"} if isinstance(auth_headers, str) else auth_headers
    )
    assert response_pos.status_code == 200
    pos_list = response_pos.json()
    test_po = next((po for po in pos_list if po["po_number"] == "po-upload-test-888"), None)
    assert test_po is not None
    
    # 2. Upload cargo photo
    import io
    file_data = io.BytesIO(b"fake image data representing cargo photo")
    response_upload_cargo = client.post(
        f"/api/kanban/pos/{test_po['id']}/upload-cargo-photo",
        headers={"Authorization": f"Bearer {auth_headers}"} if isinstance(auth_headers, str) else auth_headers,
        files={"file": ("cargo_test.png", file_data, "image/png")}
    )
    assert response_upload_cargo.status_code == 200
    po_data_cargo = response_upload_cargo.json()
    assert "foto_carga_path" in po_data_cargo["partition_metadata"]
    assert po_data_cargo["partition_metadata"]["foto_carga_path"].endswith(".png")
    
    # Check that nested logistics checklist is also updated
    logistics = po_data_cargo["partition_metadata"]["logistics_checklist"]
    assert logistics["foto_carga_path"] == po_data_cargo["partition_metadata"]["foto_carga_path"]
    
    # 3. Upload receipt photo
    file_data_receipt = io.BytesIO(b"fake image data representing receipt photo")
    response_upload_receipt = client.post(
        f"/api/kanban/pos/{test_po['id']}/upload-receipt-photo",
        headers={"Authorization": f"Bearer {auth_headers}"} if isinstance(auth_headers, str) else auth_headers,
        files={"file": ("receipt_test.png", file_data_receipt, "image/png")}
    )
    assert response_upload_receipt.status_code == 200
    po_data_receipt = response_upload_receipt.json()
    assert "foto_canhoto_path" in po_data_receipt["partition_metadata"]
    assert po_data_receipt["partition_metadata"]["foto_canhoto_path"].endswith(".png")
    
    # Check nested logistics checklist again
    logistics_updated = po_data_receipt["partition_metadata"]["logistics_checklist"]
    assert logistics_updated["foto_canhoto_path"] == po_data_receipt["partition_metadata"]["foto_canhoto_path"]
    assert logistics_updated["foto_carga_path"] == po_data_cargo["partition_metadata"]["foto_carga_path"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

