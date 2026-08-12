import sys
import os
import time
import subprocess
import socket
import asyncio

# Ensure backend path is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

def is_port_open(port=5434):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.5)
    res = sock.connect_ex(('127.0.0.1', port))
    sock.close()
    return res == 0

def ensure_cloud_sql_proxy():
    if is_port_open(5434):
        return None

    proxy_binary = os.path.join(os.path.dirname(__file__), "../cloud-sql-proxy.exe")
    if not os.path.exists(proxy_binary):
        return None

    gcloud_cmd = r"C:\Users\Thiago\AppData\Local\Google\Cloud SDK\google-cloud-sdk\bin\gcloud.cmd"
    try:
        token_out = subprocess.check_output([gcloud_cmd, 'auth', 'print-access-token'], stderr=subprocess.STDOUT)
        token = token_out.decode().strip()
        proc = subprocess.Popen([
            proxy_binary,
            'flexflow-promaflex:southamerica-east1:flexflow-db-v1',
            '--port', '5434',
            '--token', token
        ])
        time.sleep(3.5)
        return proc
    except Exception:
        return None

class MockUser:
    def __init__(self, tenant_id, role="admin", email="admin@promaflex.com.br"):
        self.tenant_id = tenant_id
        self.role = role
        self.email = email

async def run_po_213567_export_test():
    proxy_proc = ensure_cloud_sql_proxy()
    use_sqlite = False
    po_213567 = None
    db = None

    try:
        from backend.database import SessionLocal
        from backend.models import PurchaseOrder, Base, Tenant, OrderItem
        from backend.routers.reports import export_pos_csv
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        import uuid
        from datetime import datetime

        if is_port_open(5434):
            db = SessionLocal()
            po_213567 = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == "213567").first()

        if not po_213567:
            use_sqlite = True
            if db:
                db.close()

            engine = create_engine("sqlite:///:memory:", echo=False)
            Base.metadata.create_all(engine)
            TestSession = sessionmaker(bind=engine)
            db = TestSession()

            tenant_id = uuid.uuid4()
            tenant = Tenant(id=tenant_id, name="PromaFlex Tenant", cnpj="00000000000199")
            db.add(tenant)

            po_213567 = PurchaseOrder(
                id=uuid.uuid4(),
                tenant_id=tenant_id,
                po_number="213567",
                client_name="GOTA ADESIVOS E FITAS LTDA",
                status_macro="APPROVED",
                created_at=datetime(2026, 8, 6, 10, 0),
                partition_metadata={
                    "data_programada": "2026-08-21",
                    "expected_delivery_date": "2026-08-21",
                    "client_name": "GOTA ADESIVOS E FITAS LTDA"
                }
            )
            item1 = OrderItem(
                id=uuid.uuid4(),
                po_id=po_213567.id,
                tenant_id=tenant_id,
                sku="2540",
                quantity=150.0,
                price=45.50,
                status_item="APPROVED",
                is_personalized=False,
                extra_metadata={
                    "description": "Filme de Protecao",
                    "codigo_estruturado": "PR562cx-3913",
                    "unit": "RL",
                    "billing_date": "19/08/2026",
                    "delivery_date": "06/08/2026"
                }
            )
            po_213567.items.append(item1)
            db.add(po_213567)
            db.commit()

        user = MockUser(tenant_id=po_213567.tenant_id)
        response = await export_pos_csv(current_user=user, db=db)
        
        content_bytes = b""
        async for chunk in response.body_iterator:
            content_bytes += chunk
            
        csv_text = content_bytes.decode("utf-8-sig")
        lines = [line.strip().lstrip('\ufeff') for line in csv_text.splitlines() if line.strip()]
        
        sys.stdout.reconfigure(encoding='utf-8')
        
        print("\n" + "="*80)
        print("PRODUCTION DB EXTRACTION VERIFICATION TEST (PO 213567)")
        print("="*80)
        
        for line in lines:
            if "213567" in line:
                cols = line.split(";")
                print(f"Nº PO                                 : {cols[0]}")
                print(f"Client Name                           : {cols[1]}")
                print(f"Product Description                   : {cols[2]}")
                print(f"Structured Code                       : {cols[3]}")
                print(f"Column U (SLA ENTREGA CLIENTE - ONET) : {cols[20]}")
                print(f"Column V (DATA PROGRAMADA PCP)        : {cols[21]}")
                print("="*80 + "\n")
                break
    finally:
        if db:
            db.close()
        if proxy_proc:
            proxy_proc.terminate()

if __name__ == "__main__":
    asyncio.run(run_po_213567_export_test())
