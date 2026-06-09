import os
import sys
from uuid import UUID

# Add project root directory to path to import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
load_dotenv("backend/.env")

from backend.database import SessionLocal
from backend.models import Tenant, User, PurchaseOrder, OrderItem

def main():
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.name == "PromaFlex").first()
        if not tenant:
            print("Tenant PromaFlex not found!")
            return
        
        user = db.query(User).filter(User.email == "admin@botcase.com.br").first()
        if not user:
            print("User admin@botcase.com.br not found!")
            return
            
        # Check if PO already exists
        po_number = "PO-DEBUG-101"
        existing = db.query(PurchaseOrder).filter(
            PurchaseOrder.po_number == po_number,
            PurchaseOrder.tenant_id == tenant.id
        ).first()
        
        if existing:
            print(f"PO {po_number} already exists! Deleting it to recreate.")
            db.delete(existing)
            db.commit()
            
        print("Creating PO...")
        # Create PO in SHIPPING status
        po = PurchaseOrder(
            tenant_id=tenant.id,
            po_number=po_number,
            status_macro="SHIPPING",
            created_by=user.id,
            po_total_value=1500.00,
            partition_metadata={
                "client_name": "Cliente Debug S/A",
                "logistics_checklist": {
                    "endereco_conferido": True,
                    "peso_validado": True,
                    "etiquetas_impressas": True,
                    "foto_carga_path": None,
                    "foto_canhoto_path": None
                }
            }
        )
        db.add(po)
        db.commit()
        db.refresh(po)
        
        # Create Order Item
        item = OrderItem(
            po_id=po.id,
            tenant_id=tenant.id,
            sku="SKU-DEBUG-001",
            quantity=10,
            price=150.00,
            status_item="APPROVED",
            item_total_value=1500.00,
            extra_metadata={
                "cliente": "Cliente Debug S/A",
                "produto": "Material Protetivo Flex",
                "numero_nfe": "123456",
                "transportadora": "Transportadora LogFast"
            }
        )
        db.add(item)
        db.commit()
        print(f"Successfully created PurchaseOrder with ID {po.id} and po_number {po.po_number}")
    except Exception as e:
        db.rollback()
        print("Error:", e)
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
