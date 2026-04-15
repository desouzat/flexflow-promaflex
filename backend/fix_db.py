"""
Script to fix database: Change all DRAFT orders to PENDING status
"""
import sys
from pathlib import Path

# Add parent directory to path to allow backend imports
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine
from backend.models import PurchaseOrder

def fix_order_status():
    """Change all DRAFT orders to SUBMITTED (which maps to PENDING in Kanban)"""
    db: Session = SessionLocal()
    try:
        # Find all DRAFT orders
        draft_orders = db.query(PurchaseOrder).filter(
            PurchaseOrder.status_macro == 'DRAFT'
        ).all()
        
        print(f"Found {len(draft_orders)} orders with DRAFT status")
        
        # Update to SUBMITTED (which shows as PENDING in Kanban)
        for order in draft_orders:
            print(f"  Updating PO #{order.po_number}: {order.status_macro} -> SUBMITTED")
            order.status_macro = 'SUBMITTED'
        
        # Commit changes
        db.commit()
        print(f"\nOK Successfully updated {len(draft_orders)} orders to SUBMITTED status")
        
        # Verify the change
        submitted_count = db.query(PurchaseOrder).filter(
            PurchaseOrder.status_macro == 'SUBMITTED'
        ).count()
        draft_count = db.query(PurchaseOrder).filter(
            PurchaseOrder.status_macro == 'DRAFT'
        ).count()
        
        print(f"\nCurrent status:")
        print(f"  SUBMITTED orders: {submitted_count}")
        print(f"  DRAFT orders: {draft_count}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Database Fix Script: DRAFT -> PENDING")
    print("=" * 60)
    fix_order_status()
    print("=" * 60)
