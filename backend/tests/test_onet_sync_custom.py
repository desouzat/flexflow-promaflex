import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from backend.database import get_db
from backend.routers.auth import get_current_user
from backend.schemas.auth_schema import UserInfo
from backend.main import app
from backend.models import User

# Setup a clean in-memory sqlite database for unit testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_sqlite.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    from backend.models import Base
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

# Mock user info
mock_user_info = UserInfo(
    id="11111111-1111-1111-1111-111111111111",
    name="Test User",
    email="test@example.com",
    role="OPERADOR",
    tenant_id="22222222-2222-2222-2222-222222222222",
    is_sla_manager=False
)

def override_get_current_user():
    return mock_user_info

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)

def test_pending_s3_files_not_configured(monkeypatch):
    # Mock is_configured to return False
    from backend.services.s3_service import S3Service
    monkeypatch.setattr(S3Service, "is_configured", lambda self: False)
    
    response = client.get("/api/import/pending-s3-files")
    assert response.status_code == 503
    assert "S3 service not configured" in response.json()["detail"]

def test_pending_s3_files_success(monkeypatch):
    # Mock S3Service listing
    from backend.services.s3_service import S3Service
    monkeypatch.setattr(S3Service, "is_configured", lambda self: True)
    
    mock_files = [
        {
            'key': 'Exportacao_20260712_200000.xlsx',
            'size': 3307,
            'last_modified': datetime(2026, 7, 12, 20, 0, 0),
            'filename': 'Exportacao_20260712_200000.xlsx'
        },
        {
            'key': 'Exportacao_20260713_200000.xlsx',
            'size': 8500,
            'last_modified': datetime(2026, 7, 13, 20, 0, 0),
            'filename': 'Exportacao_20260713_200000.xlsx'
        }
    ]
    monkeypatch.setattr(S3Service, "list_new_files", lambda self: mock_files)
    
    response = client.get("/api/import/pending-s3-files")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    # Check parsed date
    assert data[0]["filename"] == "Exportacao_20260712_200000.xlsx"
    assert data[0]["parsed_date"] == "12/07/2026 às 20:00"
    assert data[0]["is_empty_template"] is True
    
    assert data[1]["filename"] == "Exportacao_20260713_200000.xlsx"
    assert data[1]["parsed_date"] == "13/07/2026 às 20:00"
    assert data[1]["is_empty_template"] is False

def test_sync_s3_selection(monkeypatch):
    from backend.services.s3_service import S3Service
    monkeypatch.setattr(S3Service, "is_configured", lambda self: True)
    
    mock_files = [
        {
            'key': 'Exportacao_20260712_200000.xlsx',
            'size': 3307,
            'filename': 'Exportacao_20260712_200000.xlsx'
        }
    ]
    monkeypatch.setattr(S3Service, "list_new_files", lambda self: mock_files)
    
    # Mock move_to_processed
    moved_keys = []
    monkeypatch.setattr(S3Service, "move_to_processed", lambda self, key: moved_keys.append(key))
    
    response = client.post("/api/import/sync-s3", json={"filenames": ["Exportacao_20260712_200000.xlsx"]})
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["success"] is True
    assert res_data["files_processed"] == 1
    assert "Exportacao_20260712_200000.xlsx" in moved_keys

def test_pcp_cost_lookup_permission(monkeypatch):
    db = TestingSessionLocal()
    import uuid
    test_user_pcp = User(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        email="test@example.com",
        name="Test User",
        role="OPERADOR",
        area="PCP",
        tenant_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        is_active=True,
        is_sla_manager=False,
        hashed_password="fake"
    )
    db.merge(test_user_pcp)
    db.commit()
    db.close()
    
    # Mock the MaterialCost query to avoid SQLite UUID issue
    from unittest.mock import MagicMock
    from backend.models import MaterialCost
    from sqlalchemy.orm import Session
    
    mock_query = MagicMock()
    mock_query.filter.return_value = mock_query
    mock_query.count.return_value = 0
    mock_query.order_by.return_value = mock_query
    mock_query.offset.return_value = mock_query
    mock_query.limit.return_value = mock_query
    mock_query.all.return_value = []
    
    original_query = Session.query
    def patched_query(self, *args, **kwargs):
        if args and args[0] == MaterialCost:
            return mock_query
        return original_query(self, *args, **kwargs)
        
    monkeypatch.setattr(Session, "query", patched_query)
    
    # Check permissions
    response = client.get("/api/costs/materials?sku=TEST")
    assert response.status_code == 200
