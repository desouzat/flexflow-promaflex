import os
import sys
import io
import pandas as pd
import json
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

def run_nuke_survival_verification():
    print("=" * 60)
    print("RUNNING NUKE SURVIVAL AND PRE-FILL HARNESSES (H-06 & H-07)")
    print("=" * 60)

    # 1. Login
    login_payload = {
        "email": "memory_test@example.com",
        "password": "password123"
    }
    print("Logging in...")
    login_response = client.post("/api/auth/login", json=login_payload)
    assert login_response.status_code == 200, f"Login failed: {login_response.text}"
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Login successful.")

    # 2. Database preparation
    from backend.database import SessionLocal
    from backend.models import ClientPreference, Tenant, User, PurchaseOrder, OrderItem
    from sqlalchemy import text
    import uuid

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "memory_test@example.com").first()
        tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first()

        # Clean existing test preferences to make sure count is clean
        db.query(ClientPreference).filter(
            ClientPreference.tenant_id == tenant.id,
            ClientPreference.client_name == 'TEST_INC'
        ).delete()
        db.commit()
        print("Cleaned any previous client preferences for 'TEST_INC'.")
    finally:
        db.close()

    # 3. Import PO for TEST_INC
    df = pd.DataFrame({
        'Pedido': ['po-nuke-999'],
        'Cliente': ['TEST_INC'],
        'SKU': ['SKU-MEM-1'],
        'Descrição': ['Item de teste de nuke'],
        'Qtd': [100],
        'Unidade': ['m2'],
        'Largura': [1.5],
        'Comprimento': [10.0],
        'Lead Time': [15],
        'Data Entrega': ['2026-07-01'],
        'Data Faturamento': ['2026-07-02'],
        '% ICMS': [12.0],
        'Bloqueio': ['LIBERADO'],
        'Saldo': [100.0],
        'Atraso': [0],
        'Condição Pagamento': ['30 dias'],
        'Frete': [50.0],
        'Vendedor': ['Vendedor Memorial'],
        'IPI': [5.0]
    })
    
    excel_buffer = io.BytesIO()
    df.to_excel(excel_buffer, index=False)
    excel_buffer.seek(0)
    excel_content = excel_buffer.read()

    mapping_json = {
        "mappings": [
            {"column_name": "Pedido", "field_type": "po_number"},
            {"column_name": "Cliente", "field_type": "client_name"},
            {"column_name": "SKU", "field_type": "sku"},
            {"column_name": "Descrição", "field_type": "description"},
            {"column_name": "Qtd", "field_type": "quantity"},
            {"column_name": "Unidade", "field_type": "unit"},
            {"column_name": "Largura", "field_type": "width"},
            {"column_name": "Comprimento", "field_type": "length"},
            {"column_name": "Lead Time", "field_type": "lead_time"},
            {"column_name": "Data Entrega", "field_type": "delivery_date"},
            {"column_name": "Data Faturamento", "field_type": "billing_date"},
            {"column_name": "% ICMS", "field_type": "icms_percent"},
            {"column_name": "Bloqueio", "field_type": "block_status"},
            {"column_name": "Saldo", "field_type": "balance"},
            {"column_name": "Atraso", "field_type": "delay"},
            {"column_name": "Condição Pagamento", "field_type": "payment_terms"},
            {"column_name": "Frete", "field_type": "freight"},
            {"column_name": "Vendedor", "field_type": "salesperson"},
            {"column_name": "IPI", "field_type": "ipi"}
        ]
    }

    print("Uploading PO for TEST_INC...")
    upload_response = client.post(
        "/api/import/upload",
        headers=headers,
        files={"file": ("test_nuke_1.xlsx", excel_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"mapping_json": json.dumps(mapping_json)}
    )
    assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"
    staging_po = upload_response.json()["po_list"][0]

    # Confirm staging, setting business unit to Varejo
    confirm_payload = {
        "pos": [
            {
                "po_number": staging_po["po_number"],
                "client_name": staging_po["client_name"],
                "business_unit": "Varejo",  # Set to Varejo
                "freight_cost": 150.00,
                "additional_costs": 10.00,
                "po_total_value": 1500.00,
                "packaging_type": "Palete",
                "items": [
                    {
                        "sku": item["sku"],
                        "quantity": item["quantity"],
                        "price_unit": 15.00,
                        "unit_value": 15.00,
                        "item_total_value": 1500.00,
                        "block_status": item["block_status"],
                        "balance": item["balance"],
                        "delay": item["delay"],
                        "payment_terms": item["payment_terms"],
                        "description": item["description"],
                        "unit": item["unit"],
                        "width": item["width"],
                        "length": item["length"],
                        "lead_time": item["lead_time"],
                        "delivery_date": item["delivery_date"],
                        "billing_date": item["billing_date"],
                        "icms_percent": item["icms_percent"],
                        "freight": item["freight"],
                        "salesperson": item["salesperson"],
                        "ipi": item["ipi"],
                        "extra_metadata": {
                            "is_personalized": False,
                            "is_new_client": False,
                            "is_export": False,
                            "is_replacement": False,
                            "customization_notes": ""
                        }
                    }
                    for item in staging_po["items"]
                ]
            }
        ]
    }

    print("Confirming staging PO with business_unit selected as 'Varejo'...")
    confirm_response = client.post(
        "/api/import/confirm-staging",
        headers=headers,
        json=confirm_payload
    )
    assert confirm_response.status_code == 200, f"Confirm staging failed: {confirm_response.text}"

    # 4. Trigger the database nuke
    print("Nuking tenant operational data...")
    nuke_response = client.post(
        "/api/kanban/admin/nuke-tenant-data",
        headers=headers
    )
    assert nuke_response.status_code == 200, f"Nuke failed: {nuke_response.text}"
    print("Nuke output details:", json.dumps(nuke_response.json()["details"], indent=2))

    # 5. Run SQL query: SELECT count(*) FROM client_preferences WHERE client_name = 'TEST_INC'
    db = SessionLocal()
    try:
        query_result = db.execute(
            text("SELECT count(*) FROM client_preferences WHERE client_name = 'TEST_INC'")
        ).scalar()
        print(f"SQL QUERY RESULT: SELECT count(*) FROM client_preferences WHERE client_name = 'TEST_INC' -> {query_result}")
        assert query_result == 1, f"Expected 1 client preference to survive the nuke, got {query_result}"
        print("HARNESS H-06 (Nuke Survival) PASSED!")
    finally:
        db.close()

    # 6. Harness H-07 (Pre-fill Proof): Import the PO for TEST_INC again after nuke
    # Change PO number to avoid unique constraint violations
    df['Pedido'] = 'po-nuke-999-second'
    excel_buffer2 = io.BytesIO()
    df.to_excel(excel_buffer2, index=False)
    excel_buffer2.seek(0)
    excel_content2 = excel_buffer2.read()

    print("Importing file for TEST_INC again after nuke to test pre-fill...")
    upload_response2 = client.post(
        "/api/import/upload",
        headers=headers,
        files={"file": ("test_nuke_2.xlsx", excel_content2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"mapping_json": json.dumps(mapping_json)}
    )
    assert upload_response2.status_code == 200, f"Second upload failed: {upload_response2.text}"
    upload_data2 = upload_response2.json()
    
    staging_po2 = upload_data2["po_list"][0]
    print(f"Returned business unit: {staging_po2['business_unit']}")
    
    # Assert that business unit is "Varejo" (retrieved from db preferences)
    assert staging_po2["business_unit"] == "Varejo"
    print("JSON RESPONSE PRE-FILL PROOF (H-07):")
    print(json.dumps(upload_data2, indent=2, ensure_ascii=False))
    print("HARNESS H-07 (Pre-fill Proof) PASSED!")
    print("=" * 60)

if __name__ == "__main__":
    run_nuke_survival_verification()
