import sys
import os
import uuid
from datetime import datetime

# Ensure backend path is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.models import Base, Tenant, PurchaseOrder, OrderItem
from backend.routers.reports import export_pos_csv
import asyncio

class MockUser:
    def __init__(self, tenant_id, role="admin", email="admin@promaflex.com.br"):
        self.tenant_id = tenant_id
        self.role = role
        self.email = email

async def run_sample_export():
    use_sqlite = False
    try:
        from backend.database import SessionLocal
        db = SessionLocal()
        # Test query to check if Postgres port 5434 is live
        po = db.query(PurchaseOrder).first()
        if po is None:
            use_sqlite = True
            db.close()
    except Exception:
        use_sqlite = True

    if use_sqlite:
        print("[INFO] Postgres proxy not active on port 5434. Running verification test against local SQLite DB engine.")
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        TestSession = sessionmaker(bind=engine)
        db = TestSession()

        tenant_id = uuid.uuid4()
        tenant = Tenant(id=tenant_id, name="PromaFlex Tenant", cnpj="00000000000199")
        db.add(tenant)

        # Sample PO 1 (PO 213567 with raw dt_faturamento and PCP data_programada)
        po1 = PurchaseOrder(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            po_number="213567",
            client_name="PROMA-CLIENTE ACME BRASIL",
            status_macro="APPROVED",
            created_at=datetime(2026, 8, 10, 10, 0),
            expected_delivery_date=datetime(2026, 8, 21),  # Property returns programmed date if updated
            partition_metadata={
                "data_programada": "2026-08-21",
                "client_name": "PROMA-CLIENTE ACME BRASIL",
                "dt_faturamento": "19/08/2026"
            }
        )
        item1 = OrderItem(
            id=uuid.uuid4(),
            po_id=po1.id,
            tenant_id=tenant_id,
            sku="8537",
            quantity=150.0,
            price=45.50,
            status_item="APPROVED",
            is_personalized=True,
            extra_metadata={
                "description": "FILME PROTETOR HYBRID 1200MM",
                "codigo_estruturado": "PRO-8537-1200",
                "unit": "M2",
                "largura": "1200",
                "comprimento": "100",
                "status_producao": "EM PRODUCAO",
                "qtd_real_produzida": 148,
                "perda_tecnica": 2,
                "dt_faturamento": "19/08/2026"
            }
        )
        po1.items.append(item1)
        db.add(po1)

        # Sample PO 2
        po2 = PurchaseOrder(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            po_number="213568",
            client_name="SOLUCOES PLASTICAS S.A.",
            status_macro="MANUFACTURING",
            created_at=datetime(2026, 8, 11, 14, 30),
            expected_delivery_date=datetime(2026, 8, 25),
            partition_metadata={"data_programada": "2026-08-27", "client_name": "SOLUCOES PLASTICAS S.A."}
        )
        item2 = OrderItem(
            id=uuid.uuid4(),
            po_id=po2.id,
            tenant_id=tenant_id,
            sku="9038",
            quantity=50.0,
            price=120.00,
            status_item="APPROVED",
            is_personalized=False,
            extra_metadata={
                "description": "FITA ADESIVA SLIM 500MM",
                "codigo_estruturado": "FIT-9038-500",
                "unit": "RL",
                "largura": "500",
                "comprimento": "50",
                "status_producao": "CORTE",
                "qtd_real_produzida": 50,
                "perda_tecnica": 0
            }
        )
        po2.items.append(item2)
        db.add(po2)

        # Sample PO 3
        po3 = PurchaseOrder(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            po_number="213569",
            client_name="EMBALAGENS INDUSTRIAIS LTDA",
            status_macro="BILLING",
            created_at=datetime(2026, 8, 12, 9, 15),
            expected_delivery_date=datetime(2026, 9, 1),
            partition_metadata={"data_programada": "2026-09-03", "client_name": "EMBALAGENS INDUSTRIAIS LTDA"}
        )
        item3 = OrderItem(
            id=uuid.uuid4(),
            po_id=po3.id,
            tenant_id=tenant_id,
            sku="9083",
            quantity=300.0,
            price=15.75,
            status_item="APPROVED",
            is_personalized=True,
            extra_metadata={
                "description": "BOBINA PROTECAO 800MM",
                "codigo_estruturado": "BOB-9083-800",
                "unit": "KG",
                "largura": "800",
                "comprimento": "200",
                "status_producao": "CONCLUIDO",
                "qtd_real_produzida": 300,
                "perda_tecnica": 0
            }
        )
        po3.items.append(item3)
        db.add(po3)

        db.commit()

    try:
        first_po = db.query(PurchaseOrder).first()
        user = MockUser(tenant_id=first_po.tenant_id)
        response = await export_pos_csv(current_user=user, db=db)
        
        # Collect CSV content from StreamingResponse
        content_bytes = b""
        async for chunk in response.body_iterator:
            content_bytes += chunk
            
        csv_text = content_bytes.decode("utf-8-sig")
        lines = [line.strip().lstrip('\ufeff') for line in csv_text.splitlines() if line.strip()]
        
        # Set stdout encoding for Windows terminal
        sys.stdout.reconfigure(encoding='utf-8')
        
        print("\n" + "="*80)
        print("PRACTICAL EXTRACTION VERIFICATION TEST RESULTS (PO 213567 CHECK)")
        print("="*80)
        print(f"Total Rows Generated (including header): {len(lines)}")
        print("\n--- CSV HEADER ROW ---")
        if lines:
            print(lines[0])
            
        print("\n--- EXPORTED DATA ROWS ---")
        for i, line in enumerate(lines[1:], start=1):
            print(f"Row {i}: {line}")
            if "213567" in line:
                cols = line.split(";")
                print("\n" + "-"*60)
                print("AUDIT VERIFICATION FOR PO 213567:")
                print(f"  Column U [SLA ENTREGA CLIENTE (ONET)] : {cols[20]}")
                print(f"  Column V [DATA PROGRAMADA PCP]         : {cols[21]}")
                print("-"*60 + "\n")
        print("="*80 + "\n")
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_sample_export())
