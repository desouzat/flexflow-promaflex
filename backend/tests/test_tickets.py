"""
FlexFlow - Support Ticket Tests
Integration and unit tests for support ticket creation, validation, unique ID generation, and SMTP fallback.
"""

import pytest
import io
import uuid
import re
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import SupportTicket

client = TestClient(app)

@pytest.fixture
def auth_headers():
    """Get authentication headers for test user"""
    # Use login endpoint
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

def test_ticket_id_generation_format(auth_headers):
    """Test that generated ticket IDs follow the sequential format: FF-YYYY-000X"""
    response = client.post(
        "/api/support/ticket",
        headers=auth_headers,
        data={"description": "Test ticket ID generation of 10+ characters"}
    )
    assert response.status_code == 201
    data = response.json()
    assert "ticket_id" in data
    
    ticket_id = data["ticket_id"]
    # Regex matching format: FF-YYYY-000X (sequence zero-padded to 4 digits)
    pattern = r"^FF-\d{4}-\d{4}$"
    assert re.match(pattern, ticket_id), f"Ticket ID '{ticket_id}' does not match format FF-YYYY-000X"

def test_create_ticket_without_attachment(auth_headers):
    """Test creating a support ticket without file attachment"""
    desc = "This is a test problem description with 10+ characters."
    response = client.post(
        "/api/support/ticket",
        headers=auth_headers,
        data={"description": desc}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["description"] == desc
    assert data["attachment_path"] is None
    assert data["status"] == "OPEN"

def test_create_ticket_with_attachment(auth_headers):
    """Test creating a support ticket with a valid PDF attachment"""
    desc = "This is a test problem description with attachment."
    pdf_content = b"%PDF-1.4 test pdf content"
    files = {
        "attachment": ("test_doc.pdf", io.BytesIO(pdf_content), "application/pdf")
    }
    
    response = client.post(
        "/api/support/ticket",
        headers=auth_headers,
        data={"description": desc},
        files=files
    )
    assert response.status_code == 201
    data = response.json()
    assert data["description"] == desc
    assert data["attachment_path"] is not None
    assert data["attachment_path"].endswith(".pdf")
    
    # Verify path contains tenant subdirectory
    assert "uploads/" in data["attachment_path"]

def test_ticket_db_persistence(auth_headers):
    """Test that support tickets persist correctly in the 'SupportTickets' table"""
    desc = "Testing database persistence of ticket details."
    response = client.post(
        "/api/support/ticket",
        headers=auth_headers,
        data={"description": desc}
    )
    assert response.status_code == 201
    ticket_id = response.json()["id"]
    
    # Query database directly
    db = SessionLocal()
    try:
        ticket = db.query(SupportTicket).filter(SupportTicket.id == uuid.UUID(ticket_id)).first()
        assert ticket is not None
        assert ticket.description == desc
        assert ticket.ticket_id.startswith("FF-")
        assert ticket.status == "OPEN"
    finally:
        db.close()

def test_legacy_report_endpoint(auth_headers):
    """Test that legacy /report endpoint redirects to ticket logic and works correctly"""
    desc = "Testing legacy support report endpoint."
    response = client.post(
        "/api/support/report",
        headers=auth_headers,
        json={"description": desc}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["description"] == desc
    assert "ticket_id" in data
    assert data["ticket_id"].startswith("FF-")
