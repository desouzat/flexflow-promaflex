import sys
import uuid
from pathlib import Path

# Add root folder to python path
workspace_path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(workspace_path))

from backend.database import SessionLocal
from backend.models import PurchaseOrder, AuditLog, User
from backend.routers.kanban import log_po_status_transition

class MockUserInfo:
    def __init__(self, id, role):
        self.id = id
        self.role = role

def simulate_handoff():
    db = SessionLocal()
    try:
        print("[DEBUG] Locating seeded PO: PO-CLEAN-001...")
        po = db.query(PurchaseOrder).filter(PurchaseOrder.po_number == "PO-CLEAN-001").first()
        if not po:
            print("[ERROR] PO-CLEAN-001 not found. Please run reset_demo_data.py first.")
            return

        print(f"Found PO: {po.po_number} (ID: {po.id}) in macro status: {po.status_macro}")
        
        user = db.query(User).filter(User.email == "test@example.com").first()
        current_user = MockUserInfo(user.id, user.role)
        
        from_status = po.status_macro
        to_status = "APPROVED" # PCP raia
        
        print(f"[DEBUG] Simulating handoff transition from {from_status} to {to_status}...")
        po.status_macro = to_status
        db.commit()
        
        # Log the transition physically in AuditLog V2
        log_po_status_transition(
            db=db,
            po=po,
            from_status=from_status,
            to_status=to_status,
            current_user=current_user,
            justification="Handoff test: Avanço comercial -> PCP bem-sucedido."
        )
        db.commit()
        print("[DEBUG] Handoff transaction successfully committed to the database!")

        # 3. Query the audit logs for this po_id physically via SQL
        print(f"\n--- RUNNING SQL: SELECT * FROM audit_logs WHERE extra_data->>'po_id' = '{po.id}' ---")
        from sqlalchemy import text
        
        # Query supporting dialect-agnostic JSON extracts
        sql_query = text("""
            SELECT 
                id, 
                item_id, 
                from_status, 
                to_status, 
                hash, 
                justification, 
                created_at,
                extra_data
            FROM audit_logs
        """)
        results = db.execute(sql_query).all()
        
        filtered_results = []
        for row in results:
            import json
            extra = row[7]
            if isinstance(extra, str):
                extra = json.loads(extra)
            if extra and extra.get("po_id") == str(po.id):
                filtered_results.append(row)
                
        print(f"Found {len(filtered_results)} AuditLog records for PO ID {po.id}:")
        print("-" * 120)
        print(f"{'LOG ID':<38} | {'ITEM ID':<38} | {'FROM':<10} | {'TO':<10} | {'JUSTIFICATION':<35}")
        print("-" * 120)
        for row in filtered_results:
            log_id = str(row[0])
            item_id = str(row[1])
            f_status = str(row[2])
            t_status = str(row[3])
            just = str(row[5])
            print(f"{log_id:<38} | {item_id:<38} | {f_status:<10} | {t_status:<10} | {just:<35}")
        print("-" * 120)

    except Exception as e:
        db.rollback()
        print("[ERROR] Handoff simulation failed:", e)
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    simulate_handoff()
