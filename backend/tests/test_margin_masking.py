import os
import sys
from pathlib import Path

# Add project root directory to path to import backend modules
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir.parent))

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_operator_margin_masking():
    print("=" * 60)
    print("API MARGIN MASKING HARNESS (H-03)")
    print("=" * 60)
    
    # 1. Login as operator (fabio_promaflex@grupovelletri.com.br)
    login_payload = {
        "email": "fabio_promaflex@grupovelletri.com.br",
        "password": "Proma@2026"
    }
    print(f"Logging in as operator: {login_payload['email']}...")
    login_response = client.post("/api/auth/login", json=login_payload)
    
    if login_response.status_code != 200:
        print(f"FAILED: Login returned status {login_response.status_code}")
        print(login_response.text)
        return 1
        
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful. Token obtained.")
    
    # 2. Call Kanban board endpoint
    print("Calling /api/kanban/board...")
    board_response = client.get("/api/kanban/board", headers=headers)
    assert board_response.status_code == 200, f"Board request failed with {board_response.status_code}"
    
    board_data = board_response.json()
    columns = board_data.get("columns", [])
    
    # Verify that all margins are masked on the board
    checked_pos = 0
    checked_items = 0
    
    for column in columns:
        pos = column.get("pos", [])
        for po in pos:
            checked_pos += 1
            # Check PO global margins
            assert po.get("margin_global") == "***", f"PO margin_global not masked: {po.get('margin_global')}"
            assert po.get("margin_percentage") == "***", f"PO margin_percentage not masked: {po.get('margin_percentage')}"
            
            # Check PO items
            for item in po.get("items", []):
                checked_items += 1
                assert item.get("margin_item") == "***", f"Item margin_item not masked: {item.get('margin_item')}"
                
    print(f"Verified {checked_pos} POs and {checked_items} items on Kanban board.")
    
    # 3. Call list purchase orders endpoint
    print("Calling /api/kanban/pos...")
    pos_response = client.get("/api/kanban/pos", headers=headers)
    assert pos_response.status_code == 200, f"POS request failed with {pos_response.status_code}"
    pos_list = pos_response.json()
    
    for po in pos_list:
        assert po.get("margin_global") == "***", f"POS list po margin_global not masked: {po.get('margin_global')}"
        assert po.get("margin_percentage") == "***", f"POS list po margin_percentage not masked: {po.get('margin_percentage')}"
        for item in po.get("items", []):
            assert item.get("margin_item") == "***", f"POS list item margin_item not masked: {item.get('margin_item')}"
            
    print(f"Verified {len(pos_list)} POs on /api/kanban/pos endpoint.")
    print("API MASKING STATUS: SECURED AND VERIFIED!")
    return 0

if __name__ == "__main__":
    sys.exit(test_operator_margin_masking())
