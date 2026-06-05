import pytest
from fastapi.testclient import TestClient
import io
import uuid
import pandas as pd
import json
from backend.main import app

client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_test_user_and_db():
    from backend.database import SessionLocal, engine, Base
    from backend.models import Tenant, User, ClientPreference, PurchaseOrder, OrderItem

    # Create tables if not exists
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Check if tenant exists
        tenant = db.query(Tenant).filter(Tenant.cnpj == "55.555.555/0001-55").first()
        if not tenant:
            tenant = Tenant(
                id=uuid.uuid4(),
                name="PromaMemoryTenant",
                cnpj="55.555.555/0001-55",
                is_active=True
            )
            db.add(tenant)
            db.flush()

        # Check if user exists
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
        user = db.query(User).filter(User.email == "memory_test@example.com").first()
        if not user:
            user = User(
                id=uuid.uuid4(),
                tenant_id=tenant.id,
                name="Memory Test User",
                email="memory_test@example.com",
                hashed_password=pwd_context.hash("password123"),
                role="admin",
                is_active=True
            )
            db.add(user)
            db.flush()

        # Clean any existing client preferences or POs for this test client
        test_client_name = "Cliente Memorial Industria LTDA"
        db.query(ClientPreference).filter(
            ClientPreference.tenant_id == tenant.id,
            ClientPreference.client_name == test_client_name
        ).delete()

        db.commit()
    finally:
        db.close()

@pytest.fixture
def auth_headers():
    response = client.post(
        "/api/auth/login",
        json={
            "email": "memory_test@example.com",
            "password": "password123"
        }
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

def test_client_business_unit_memory_lifecycle(auth_headers):
    print("\n" + "=" * 60)
    print("RUNNING MEMORY PROOF HARNESS (H-04)")
    print("=" * 60)

    # 1. Create a mock Excel sheet using the 22-field structure or simple structure
    # Column mapping is needed to match what is parsed
    df = pd.DataFrame({
        'Pedido': ['po-memory-1001'],
        'Cliente': ['Cliente Memorial Industria LTDA'],
        'SKU': ['SKU-MEM-1'],
        'Descrição': ['Item de teste de memoria'],
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

    # First import: Upload the file
    print("1. Uploading first file for Cliente Memorial Industria LTDA...")
    upload_response = client.post(
        "/api/import/upload",
        headers=auth_headers,
        files={"file": ("test_memory_1.xlsx", excel_content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"mapping_json": json.dumps(mapping_json)}
    )
    assert upload_response.status_code == 200, f"Upload failed: {upload_response.text}"
    upload_data = upload_response.json()
    
    # Verify staging classification defaulted to Indústria (via LTDA regex mapping fallback)
    staging_po = upload_data["po_list"][0]
    print(f"Staging pre-filled business unit (fallback classification): {staging_po['business_unit']}")
    assert staging_po["business_unit"] == "Indústria"

    # Confirm staging PO, specifying "Varejo" instead of "Indústria" to verify that manual selection overwrites preference
    confirm_payload = {
        "pos": [
            {
                "po_number": staging_po["po_number"],
                "client_name": staging_po["client_name"],
                "business_unit": "Varejo",  # Override manually
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

    print("2. Confirming staging PO with business_unit manually selected as 'Varejo'...")
    confirm_response = client.post(
        "/api/import/confirm-staging",
        headers=auth_headers,
        json=confirm_payload
    )
    assert confirm_response.status_code == 200, f"Confirm staging failed: {confirm_response.text}"

    # Verify preference was written to database
    from backend.database import SessionLocal
    from backend.models import ClientPreference, Tenant
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.cnpj == "55.555.555/0001-55").first()
        pref = db.query(ClientPreference).filter(
            ClientPreference.tenant_id == tenant.id,
            ClientPreference.client_name == "Cliente Memorial Industria LTDA"
        ).first()
        assert pref is not None, "ClientPreference was not created in database!"
        print(f"Verified preference in database: client='{pref.client_name}', business_unit='{pref.business_unit}'")
        assert pref.business_unit == "Varejo"
    finally:
        db.close()

    # Second import: Upload a new PO for the SAME client name
    # Change PO number to avoid unique constraint violations
    df['Pedido'] = 'po-memory-1002'
    excel_buffer2 = io.BytesIO()
    df.to_excel(excel_buffer2, index=False)
    excel_buffer2.seek(0)
    excel_content2 = excel_buffer2.read()

    print("3. Uploading second file for the same client to test pre-fill memory...")
    upload_response2 = client.post(
        "/api/import/upload",
        headers=auth_headers,
        files={"file": ("test_memory_2.xlsx", excel_content2, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        data={"mapping_json": json.dumps(mapping_json)}
    )
    assert upload_response2.status_code == 200, f"Second upload failed: {upload_response2.text}"
    upload_data2 = upload_response2.json()
    
    staging_po2 = upload_data2["po_list"][0]
    print(f"Second staging pre-filled business unit (from memory preference): {staging_po2['business_unit']}")
    
    # Assert that business unit is "Varejo" (retrieved from db preferences, and NOT classified as "Indústria" anymore!)
    assert staging_po2["business_unit"] == "Varejo"
    print("SUCCESS: Memory proof verified! Client preferences retrieved from database on second import.")
    print("=" * 60)

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])
