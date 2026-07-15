import os
import sys
from pathlib import Path
from sqlalchemy import text

# Fix Windows console encoding issues
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory of backend (workspace root) to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from backend.database import SessionLocal

# Enforce Dry-Run Mode by default
DRY_RUN = True

TARGET_POS = [
    "213095", "213094", "213093", "213092", "213090", "213089", "213088", "213087", "213086", "213085",
    "213084", "213083", "213082", "213081", "213080", "213079", "213077", "213076", "213075", "213074",
    "213073", "213072", "213071", "213070", "213069", "213068", "213067", "213066", "213065", "213064",
    "213063", "213062", "213060", "213059", "213061", "213036", "213035", "213034", "213033", "213032",
    "213031", "213030", "213029", "213028", "213027", "213026", "213025", "213024", "213023", "213021",
    "213020", "213018", "213017", "213016", "213015", "213019"
]

THIAGO_UUID = "a39e3176-55ac-460e-bcd2-958068737b0b"

def run_purge():
    print("=" * 90)
    print(f"🧹 PURGE TEST COSTS UTILITY (DRY_RUN = {DRY_RUN})")
    print("=" * 90)
    
    db = SessionLocal()
    try:
        # Fetch username mapping
        users_res = db.execute(text("SELECT id, name, email FROM users")).fetchall()
        user_map = {str(u[0]): f"{u[1]} ({u[2]})" for u in users_res}
        user_map[THIAGO_UUID] = "Thiago BotCase (thiago@botcase.net)"
        
        pos_str = ", ".join(f"'{p}'" for p in TARGET_POS)
        
        # Query items and their current costs
        query = text(f"""
            SELECT po.po_number, oi.id, oi.sku, mc.custo_mp_kg, mc.rendimento, mc.updated_by, mc.id
            FROM purchase_orders po
            JOIN order_items oi ON po.id = oi.po_id
            LEFT JOIN material_costs mc ON oi.sku = mc.sku AND oi.tenant_id = mc.tenant_id
            WHERE po.po_number IN ({pos_str})
            ORDER BY po.po_number, oi.sku;
        """)
        
        rows = db.execute(query).fetchall()
        total_items = len(rows)
        
        print(f"\nTarget POs: {len(TARGET_POS)}")
        print(f"Total items found: {total_items}\n")
        
        # Table Header
        print(f"{'PO Number':<10} | {'Item SKU':<12} | {'Current Cost':<15} | {'Linked By':<45} | {'Will Clear?':<12}")
        print("-" * 105)
        
        flagged_for_clear = 0
        left_untouched = 0
        unlinked = 0
        
        skus_to_clear = set()
        
        for r in rows:
            po_num, item_id, sku, custo, rendimento, updated_by, mc_id = r
            
            # Format current cost
            if custo is not None and rendimento is not None:
                current_cost = f"R$ {custo:.2f} / {rendimento:.4f}"
            else:
                current_cost = "Sem Custo"
                
            updated_by_str = str(updated_by) if updated_by else None
            linked_by = user_map.get(updated_by_str, "Sistema / Outro") if updated_by_str else "Não Vinculado"
            
            if updated_by_str == THIAGO_UUID:
                will_clear = "YES"
                flagged_for_clear += 1
                skus_to_clear.add((sku, mc_id))
            elif updated_by_str is not None:
                will_clear = "NO"
                left_untouched += 1
            else:
                will_clear = "NO"
                unlinked += 1
                
            print(f"{po_num:<10} | {sku:<12} | {current_cost:<15} | {linked_by:<45} | {will_clear:<12}")
            
        print("-" * 105)
        print("\nSummary Statistics:")
        print(f"  Total items found: {total_items}")
        print(f"  Items flagged for clear (Thiago BotCase): {flagged_for_clear}")
        print(f"  Items left untouched (linked by real operators): {left_untouched}")
        print(f"  Items already without link: {unlinked}")
        print(f"  Unique SKUs to reset: {len(skus_to_clear)}")
        
        if flagged_for_clear > 0:
            if DRY_RUN:
                print("\n[INFO] DRY_RUN is active. No modifications have been committed to the database.")
            else:
                print("\n[ACTION] Resetting cost fields for flagged SKUs in database...")
                for sku, mc_id in skus_to_clear:
                    # Reset values in material_costs to 0
                    db.execute(text(
                        "UPDATE material_costs "
                        "SET custo_mp_kg = 0.00, rendimento = 1.0000, updated_by = NULL, updated_at = NOW() "
                        "WHERE id = :mc_id"
                    ), {"mc_id": mc_id})
                db.commit()
                print("✅ Database successfully updated and committed!")
        else:
            print("\n[INFO] No items flagged for clearing.")
            
    except Exception as e:
        db.rollback()
        print(f"❌ Error during purge execution: {e}")
    finally:
        db.close()
        print("=" * 90)

if __name__ == "__main__":
    # If "--execute" argument is passed, turn off DRY_RUN
    if len(sys.argv) > 1 and sys.argv[1] == "--execute":
        DRY_RUN = False
    run_purge()
