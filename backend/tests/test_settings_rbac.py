"""
FlexFlow - Settings RBAC Validation Harness (H-12)
Verifies that settings retrieval and modifications are restricted strictly to role 'admin',
and blocked (403 Forbidden) for 'master' and 'operator' roles.
"""

import pytest
import uuid
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal, engine, Base
from backend.models import Tenant, User
from passlib.context import CryptContext

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_rbac_users():
    """Seed users with admin, master, and operator roles for testing settings API"""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
    
    try:
        # 1. Get or create test tenant
        tenant = db.query(Tenant).filter(Tenant.cnpj == "12.345.678/0001-90").first()
        if not tenant:
            tenant = Tenant(
                id=uuid.uuid4(),
                name="PromaFlex Settings",
                cnpj="12.345.678/0001-90",
                is_active=True
            )
            db.add(tenant)
            db.flush()
            
        # 2. Seed Admin User
        admin_email = "admin_settings@example.com"
        admin = db.query(User).filter(User.email == admin_email).first()
        if not admin:
            admin = User(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                name="Admin User Settings",
                email=admin_email,
                hashed_password=pwd_context.hash("password123"),
                role="admin",
                is_active=True
            )
            db.add(admin)
            
        # 3. Seed Master User
        master_email = "master_settings@example.com"
        master = db.query(User).filter(User.email == master_email).first()
        if not master:
            master = User(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                name="Master User Settings",
                email=master_email,
                hashed_password=pwd_context.hash("password123"),
                role="master",
                is_active=True
            )
            db.add(master)
            
        # 4. Seed Operator User
        operator_email = "operator_settings@example.com"
        operator = db.query(User).filter(User.email == operator_email).first()
        if not operator:
            operator = User(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                name="Operator User Settings",
                email=operator_email,
                hashed_password=pwd_context.hash("password123"),
                role="operator",
                is_active=True
            )
            db.add(operator)
            
        db.commit()
    finally:
        db.close()

def get_auth_headers(email, password="password123"):
    """Helper to authenticate a user and get headers"""
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password}
    )
    assert response.status_code == 200, f"Login failed for {email}"
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_admin_access():
    """Verify that an 'admin' role can read and update settings"""
    headers = get_auth_headers("admin_settings@example.com")
    
    # 1. Fetch support email (GET)
    response = client.get("/api/settings/support-email", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "support_email" in data
    
    # 2. Update support email (POST)
    new_email = "new_support_admin@botcase.net"
    response = client.post(
        "/api/settings/support-email",
        headers=headers,
        json={"support_email": new_email}
    )
    assert response.status_code == 200
    assert response.json()["support_email"] == new_email
    
    # 3. Verify modification persisted
    response = client.get("/api/settings/support-email", headers=headers)
    assert response.status_code == 200
    assert response.json()["support_email"] == new_email

def test_master_access_denied():
    """Verify that a 'master' role CANNOT access or update settings (403)"""
    headers = get_auth_headers("master_settings@example.com")
    
    # 1. Attempt GET -> should be 403 Forbidden
    response = client.get("/api/settings/support-email", headers=headers)
    assert response.status_code == 403, f"Expected 403 but got {response.status_code}"
    
    # 2. Attempt POST -> should be 403 Forbidden
    response = client.post(
        "/api/settings/support-email",
        headers=headers,
        json={"support_email": "master_hack@botcase.net"}
    )
    assert response.status_code == 403, f"Expected 403 but got {response.status_code}"

def test_operator_access_denied():
    """Verify that an 'operator' role CANNOT access or update settings (403)"""
    headers = get_auth_headers("operator_settings@example.com")
    
    # 1. Attempt GET -> should be 403 Forbidden
    response = client.get("/api/settings/support-email", headers=headers)
    assert response.status_code == 403, f"Expected 403 but got {response.status_code}"
    
    # 2. Attempt POST -> should be 403 Forbidden
    response = client.post(
        "/api/settings/support-email",
        headers=headers,
        json={"support_email": "operator_hack@botcase.net"}
    )
    assert response.status_code == 403, f"Expected 403 but got {response.status_code}"
