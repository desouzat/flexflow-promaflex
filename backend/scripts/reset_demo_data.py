import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Add root folder to python path
workspace_path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(workspace_path))

from backend.database import SessionLocal
from backend.models import Tenant, User, PurchaseOrder, OrderItem, AuditLog

class MockUserInfo:
    def __init__(self, id, role):
        self.id = id
        self.role = role

def reset_demo_data():
    db = SessionLocal()
    try:
        print("[DEBUG] Scrubbing database records...")
        # 1. Delete all existing AuditLogs, OrderItems, and PurchaseOrders
        db.query(AuditLog).delete()
        db.query(OrderItem).delete()
        db.query(PurchaseOrder).delete()
        db.commit()
        print("[DEBUG] Existing AuditLogs, OrderItems, and PurchaseOrders successfully scrubbed.")

        # 2. Get/create a valid Tenant and User for seeding
        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(id=uuid.uuid4(), name="Default Tenant")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            
        user = db.query(User).filter(User.email == "test@example.com").first()
        if not user:
            from backend.routers.auth import get_password_hash
            user = User(
                id=uuid.uuid4(),
                email="test@example.com",
                name="Test User",
                hashed_password=get_password_hash("password123"),
                role="admin",
                tenant_id=tenant.id
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        print("[DEBUG] Creating 3 new Purchase Orders with complete data...")

        # PO 1: Comercial Stage (DRAFT)
        po1 = PurchaseOrder(
            id=uuid.uuid4(),
            po_number="PO-CLEAN-001",
            status_macro="DRAFT",
            tenant_id=tenant.id,
            created_by=user.id,
            created_at=datetime.utcnow() - timedelta(days=2),
            partition_metadata={
                "client_name": "Promaflex Industrial Ltda",
                "expected_delivery_date": (datetime.utcnow() + timedelta(days=15)).strftime("%Y-%m-%dT00:00:00"),
                "priority_note": ""
            }
        )
        db.add(po1)

        # PO 2: PCP Stage (APPROVED status_macro)
        po2 = PurchaseOrder(
            id=uuid.uuid4(),
            po_number="PO-CLEAN-002",
            status_macro="APPROVED",
            tenant_id=tenant.id,
            created_by=user.id,
            created_at=datetime.utcnow() - timedelta(days=5),
            partition_metadata={
                "client_name": "Antigravity Aero Soluções",
                "expected_delivery_date": (datetime.utcnow() + timedelta(days=10)).strftime("%Y-%m-%dT00:00:00"),
                "priority_note": "",
                "packaging_type": "Madeira Especial",
                "data_programada": (datetime.utcnow() + timedelta(days=10)).strftime("%Y-%m-%d")
            }
        )
        db.add(po2)

        # PO 3: Expedição Stage (WAITING_DISPATCH)
        po3 = PurchaseOrder(
            id=uuid.uuid4(),
            po_number="PO-CLEAN-003",
            status_macro="WAITING_DISPATCH",
            tenant_id=tenant.id,
            created_by=user.id,
            created_at=datetime.utcnow() - timedelta(days=1),
            partition_metadata={
                "client_name": "Thiago Solutions SE",
                "expected_delivery_date": (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%dT00:00:00"),
                "priority_note": "",
                "numero_nfe": "123456",
                "chave_acesso": "12345678901234567890123456789012345678901234", # 44 digits
                "transportadora": "Frete Rápido Ltda",
                "logistics_checklist": {
                    "endereco_conferido": True,
                    "peso_validado": True,
                    "etiquetas_impressas": True,
                    "foto_carga_path": "/uploads/carga_mock.jpg",
                    "foto_canhoto_path": "/uploads/canhoto_mock.jpg"
                }
            }
        )
        db.add(po3)
        db.commit()

        # Add items and log creation transitions
        from backend.routers.kanban import log_po_status_transition
        current_user = MockUserInfo(user.id, user.role)
        
        pos = [po1, po2, po3]
        for po in pos:
            item = OrderItem(
                id=uuid.uuid4(),
                po_id=po.id,
                tenant_id=tenant.id,
                sku="FLX-MOCK-999",
                quantity=100,
                price=150.00,
                status_item="PENDING",
                unit_value=150.00,
                item_total_value=15000.00,
                extra_metadata={
                    "is_export": False,
                    "is_urgent": False,
                    "is_first_order": True,
                    "is_replacement": False,
                    "ipi": 5.0,
                    "unit": "M2",
                    "width": 1.20,
                    "length": 100.0,
                    "balance": 100
                }
            )
            db.add(item)
            db.commit() # commit item so relation is resolved cleanly
            
            # Re-fetch po with items populated
            db.refresh(po)
            
            # Log transition from None to macro status
            log_po_status_transition(
                db=db,
                po=po,
                from_status=None,
                to_status=po.status_macro,
                current_user=current_user,
                justification="Pedido criado no sistema com dados V2 completos."
            )
            
        db.commit()
        print("[DEBUG] Successfully seeded database with 3 clean Purchase Orders, OrderItems, and initial AuditLogs!")

    except Exception as e:
        db.rollback()
        print("[ERROR] Database reset failed:", e)
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    reset_demo_data()
