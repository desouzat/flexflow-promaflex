import os
import sys
import io
import pandas as pd
from pathlib import Path

# Add project root to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir.parent))

# Apply httpx monkeypatch to avoid TypeError
import httpx
_original_init = httpx.Client.__init__
def _patched_init(self, *args, **kwargs):
    kwargs.pop('app', None)
    _original_init(self, *args, **kwargs)
httpx.Client.__init__ = _patched_init

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def run_verify_cost_upload():
    print("=" * 60)
    print("RUNNING COST UPSERT PROOF HARNESS (H-05)")
    print("=" * 60)

    # 1. Login as admin/master
    login_payload = {
        "email": "admin@botcase.com.br",
        "password": "Admin@2026"  # Official admin credentials
    }
    print("Logging in as admin...")
    login_response = client.post("/api/auth/login", json=login_payload)
    if login_response.status_code != 200:
        # Fallback to test user if admin seed is different
        login_response = client.post(
            "/api/auth/login",
            json={"email": "memory_test@example.com", "password": "password123"}
        )
    
    assert login_response.status_code == 200, f"Login failed: {login_response.text}"
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful.")

    # 2. Setup a purchase order in the database containing the SKU we will update,
    # ensuring it starts as PENDENTE PCP by having a missing/zero cost or just showing it's in the board.
    from backend.database import SessionLocal
    from backend.models import PurchaseOrder, OrderItem, MaterialCost, Tenant, User
    import uuid
    from decimal import Decimal

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "memory_test@example.com").first()
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()

        # Let's delete existing test costs if any to be clean
        db.query(MaterialCost).filter(
            MaterialCost.tenant_id == tenant.id,
            MaterialCost.sku == "NEW-SKU-9999"
        ).delete()
        
        # Ensure PP-1000 exists
        mc_existing = db.query(MaterialCost).filter(
            MaterialCost.tenant_id == tenant.id,
            MaterialCost.sku == "PP-1000"
        ).first()
        if not mc_existing:
            mc_existing = MaterialCost(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                sku="PP-1000",
                nome="Polipropileno Natural",
                custo_mp_kg=8.50,
                rendimento=0.92,
                indice_impostos=22.25,
                updated_by=user.id
            )
            db.add(mc_existing)
            db.flush()

        # Seed a test purchase order with PENDENTE PCP status by having a new SKU with no cost yet
        po_number_cleanup = "PO-CLEANUP-8888"
        db.query(PurchaseOrder).filter(
            PurchaseOrder.tenant_id == tenant.id,
            PurchaseOrder.po_number == po_number_cleanup
        ).delete()
        db.flush()

        test_po = PurchaseOrder(
            id=uuid.uuid4(),
            tenant_id=tenant.id,
            po_number=po_number_cleanup,
            status_macro="APPROVED",  # PCP column
            created_by=user.id,
            shipping_cost=100.0,
            po_total_value=1200.0
        )
        db.add(test_po)
        db.flush()

        item_cleanup = OrderItem(
            id=uuid.uuid4(),
            po_id=test_po.id,
            tenant_id=tenant.id,
            sku="NEW-SKU-9999",  # Not in cost table yet!
            quantity=10,
            price=120.0,
            status_item="PENDING",
            unit_value=120.0,
            item_total_value=1200.0
        )
        db.add(item_cleanup)
        db.commit()
        print(f"Seeded test PO {po_number_cleanup} containing NEW-SKU-9999 (currently pending costs).")
    finally:
        db.close()

    # 3. Create Excel data following strict Celso layout:
    # Column A: 'Material'
    # Column B: 'Rendimento'
    # Column C: Empty or placeholder
    # Column D: 'CUSTO KG'
    # Row 1: PP-1000 (update)
    # Row 2: NEW-SKU-9999 (create)
    df = pd.DataFrame({
        'Material': ['PP-1000', 'NEW-SKU-9999'],
        'Rendimento': [0.95, 0.88],
        'Unnamed: 2': ['-', '-'],  # Column C (ignored)
        'CUSTO KG': [9.00, 11.50]
    })

    excel_buffer = io.BytesIO()
    # Write Excel with correct headers
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    
    excel_buffer.seek(0)
    excel_content = excel_buffer.read()

    # 4. Upload file
    print("Uploading Excel file to /api/costs/upload...")
    upload_response = client.post(
        "/api/costs/upload",
        headers=headers,
        files={"file": ("custos_celso.xlsx", excel_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )

    print("Response Status Code:", upload_response.status_code)
    print("Response Body:")
    import json
    print(json.dumps(upload_response.json(), indent=2, ensure_ascii=False))

    assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"
    response_data = upload_response.json()
    assert response_data["created"] == 1, f"Expected 1 created, got {response_data['created']}"
    assert response_data["updated"] == 1, f"Expected 1 updated, got {response_data['updated']}"
    print("=" * 60)
    print("COST UPSERT PROOF HARNESS (H-05) PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    run_verify_cost_upload()
