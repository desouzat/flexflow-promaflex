"""
Security and Authentication boundary tests.
Verifies that protected endpoints return 401/403 when accessed without valid credentials or tokens.
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

# Protected endpoints to check
PROTECTED_ENDPOINTS = [
    ("/api/auth/me", "GET"),
    ("/api/kanban/board", "GET"),
    ("/api/kanban/pos", "GET"),
    ("/api/kanban/pos/00000000-0000-0000-0000-000000000001", "GET"),
    ("/api/kanban/move-status", "POST"),
    ("/api/dashboard/metrics", "GET"),
    ("/api/dashboard/summary", "GET"),
    ("/api/costs/materials", "GET"),
    ("/api/partition/suggest", "POST"),
    ("/api/partition/pending", "GET"),
]

def test_endpoints_without_token():
    """Verify that all protected endpoints return 401 or 403 when called without an Authorization header."""
    for path, method in PROTECTED_ENDPOINTS:
        if method == "GET":
            response = client.get(path)
        elif method == "POST":
            response = client.post(path, json={})
        
        # Must be either 401 Unauthorized (invalid/missing credentials) or 403 Forbidden
        assert response.status_code in [401, 403], f"Endpoint {method} {path} returned status {response.status_code} instead of 401/403"


def test_endpoints_with_invalid_token():
    """Verify that all protected endpoints return 401 or 403 when called with an invalid token."""
    headers = {"Authorization": "Bearer invalid-or-expired-token"}
    for path, method in PROTECTED_ENDPOINTS:
        if method == "GET":
            response = client.get(path, headers=headers)
        elif method == "POST":
            response = client.post(path, json={}, headers=headers)
        
        assert response.status_code in [401, 403], f"Endpoint {method} {path} returned status {response.status_code} instead of 401/403"
