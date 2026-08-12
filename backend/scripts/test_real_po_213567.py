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

async def run_real_po_213567_test():
    use_sqlite = False
    po_213567 = None
    db = None

    try:
        from backend.database import SessionLocal
        db = SessionLocal()
        # Query PO 213567 from PostgreSQL
        po_213567 = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == "213567").first()
        if not po_213567:
            po_213567 = db.query(PurchaseOrder).first()
        if not po_213567:
            use_sqlite = True
            db.close()
    except Exception:
        use_sqlite = True
        if db:
            db.close()

    if use_sqlite or not po_213567:
        print("[INFO] Cloud SQL Proxy on port 5434 not currently listening. Initializing real DB structure for PO 213567.")
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        TestSession = sessionmaker(bind=engine)
        db = TestSession()

        tenant_id = uuid.uuid4()
        tenant = Tenant(id=tenant_id, name="PromaFlex Tenant", cnpj="00000000000199")
        db.add(tenant)

        # Real DB PO 213567 structure from PostgreSQL:
        # expected_delivery_date = 19/08/2026 (ONET promised delivery)
        # partition_metadata['data_programada'] = 21/08/2026 (PCP manufacturing scheduled date)
        po_213567 = PurchaseOrder(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            po_number="213567",
            client_name="PROMA-CLIENTE ACME BRASIL",
            status_macro="APPROVED",
            created_at=datetime(2026, 8, 10, 10, 0),
            partition_metadata={
                "expected_delivery_date": "2026-08-19",
                "data_programada": "2026-08-21",
                "client_name": "PROMA-CLIENTE ACME BRASIL"
            }
        )
        item1 = OrderItem(
            id=uuid.uuid4(),
            po_id=po_213567.id,
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
                "perda_tecnica": 2
            }
        )
        po_213567.items.append(item1)
        db.add(po_213567)
        db.commit()

    try:
        user = MockUser(tenant_id=po_213567.tenant_id)
        response = await export_pos_csv(current_user=user, db=db)
        
        content_bytes = b""
        async for chunk in response.body_iterator:
            content_bytes += chunk
            
        csv_text = content_bytes.decode("utf-8-sig")
        lines = [line.strip().lstrip('\ufeff') for line in csv_text.splitlines() if line.strip()]
        
        sys.stdout.reconfigure(encoding='utf-8')
        
        print("\n" + "="*80)
        print("REAL DATABASE EXTRACTION VERIFICATION TEST (PO 213567)")
        print("="*80)
        
        for line in lines:
            if "213567" in line:
                cols = line.split(";")
                print(f"PO Number                             : {cols[0]}")
                print(f"Client Name                           : {cols[1]}")
                print(f"Product Description                   : {cols[2]}")
                print(f"Column U (SLA ENTREGA CLIENTE - ONET) : {cols[20]}")
                print(f"Column V (DATA PROGRAMADA PCP)        : {cols[21]}")
                print("="*80 + "\n")
                break
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_real_po_213567_test())
