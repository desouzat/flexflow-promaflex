"""
FlexFlow - Settings and Ticket Simulation (H-13)
Updates support email to test@botcase.net and submits a support ticket to verify simulated email routing.
"""

import sys
import httpx

# Patch httpx.Client to prevent Starlette TestClient incompatibility in this environment
_original_init = httpx.Client.__init__
def _patched_init(self, *args, **kwargs):
    kwargs.pop('app', None)
    _original_init(self, *args, **kwargs)
httpx.Client.__init__ = _patched_init

from fastapi.testclient import TestClient
from backend.main import app

def run_simulation():
    client = TestClient(app)
    
    print("1. Logging in as admin...")
    login_response = client.post(
        "/api/auth/login",
        json={
            "email": "test@example.com",
            "password": "password123"
        }
    )
    if login_response.status_code != 200:
        print(f"Login failed: {login_response.text}")
        return
        
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful.")
    
    print("\n2. Changing support email to test@botcase.net in Settings...")
    settings_response = client.post(
        "/api/settings/support-email",
        headers=headers,
        json={"support_email": "test@botcase.net"}
    )
    if settings_response.status_code != 200:
        print(f"Failed to update support email: {settings_response.text}")
        return
    print(f"Settings updated: {settings_response.json()}")
    
    print("\n3. Creating a support ticket...")
    # Create ticket (which triggers simulated email output to console)
    ticket_response = client.post(
        "/api/support/ticket",
        headers=headers,
        data={"description": "Simulated ticket for testing Settings parameterization H-13."}
    )
    if ticket_response.status_code != 201:
        print(f"Failed to create support ticket: {ticket_response.text}")
        return
        
    ticket_data = ticket_response.json()
    print(f"Ticket created successfully! ID: {ticket_data['ticket_id']}")
    print("\n4. Checking email output above. Done.")

if __name__ == "__main__":
    run_simulation()
