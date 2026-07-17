import sys
import io
import os
import uuid
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Ensure we can load env
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir.parent))

from backend.database import SQLALCHEMY_DATABASE_URL

def main():
    print("=" * 60)
    print("SKU DOT SANITIZATION MIGRATION SCRIPT")
    print(f"Target Connection: {SQLALCHEMY_DATABASE_URL}")
    print("=" * 60)
    
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"connect_timeout": 10})
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Action A: Sanitize and Merge material_costs
        print("\n[ACTION A] Sanitizing material_costs table...")
        
        # Get all material_costs
        materials = session.execute(text("SELECT id, sku, nome, custo_mp_kg, rendimento, indice_impostos, tenant_id, updated_by FROM material_costs")).fetchall()
        
        updated_materials_count = 0
        merged_materials_count = 0
        deleted_materials_count = 0
        
        for mat in materials:
            mat_id, sku, nome, custo, rendimento, impostos, tenant_id, updated_by = mat
            if sku and '.' in sku:
                clean_sku = sku.replace('.', '')
                print(f"Found SKU with dot: '{sku}' -> clean target: '{clean_sku}'")
                
                # Check if clean SKU already exists
                existing = session.execute(
                    text("SELECT id, sku, nome, custo_mp_kg, rendimento, indice_impostos FROM material_costs WHERE tenant_id = :tenant_id AND sku = :sku"),
                    {"tenant_id": tenant_id, "sku": clean_sku}
                ).fetchone()
                
                if existing:
                    existing_id, ex_sku, ex_name, ex_custo, ex_rendimento, ex_impostos = existing
                    print(f"  Clean SKU '{clean_sku}' already exists with ID {existing_id} (Cost: R$ {ex_custo})")
                    
                    # Merge strategy: retain the one with cost > 0
                    if custo > 0 and ex_custo == 0:
                        print(f"  -> Merging: Updating clean SKU '{clean_sku}' to have new cost: {custo}, rendimento: {rendimento}, impostos: {impostos}, nome: '{nome}'")
                        session.execute(
                            text("""
                                UPDATE material_costs 
                                SET custo_mp_kg = :custo, 
                                    rendimento = :rendimento, 
                                    indice_impostos = :impostos, 
                                    nome = :nome,
                                    updated_at = NOW(),
                                    updated_by = :updated_by
                                WHERE id = :existing_id
                            """),
                            {
                                "custo": custo,
                                "rendimento": rendimento,
                                "impostos": impostos,
                                "nome": nome,
                                "updated_by": updated_by,
                                "existing_id": existing_id
                            }
                        )
                        merged_materials_count += 1
                    else:
                        print(f"  -> Retaining existing clean SKU '{clean_sku}' (existing cost {ex_custo} >= current {custo})")
                    
                    # Delete the dot-containing record
                    print(f"  -> Deleting redundant dot-containing SKU record '{sku}' (ID: {mat_id})")
                    session.execute(
                        text("DELETE FROM material_costs WHERE id = :id"),
                        {"id": mat_id}
                    )
                    deleted_materials_count += 1
                else:
                    # No clean version exists, just update SKU
                    print(f"  -> No clean SKU exists. Updating '{sku}' to '{clean_sku}'")
                    session.execute(
                        text("UPDATE material_costs SET sku = :clean_sku, updated_at = NOW() WHERE id = :id"),
                        {"clean_sku": clean_sku, "id": mat_id}
                    )
                    updated_materials_count += 1
                    
        # Action B: Sanitize order_items
        print("\n[ACTION B] Sanitizing order_items table...")
        
        # Get all order_items with dots in SKU
        items_with_dots = session.execute(text("SELECT id, sku FROM order_items WHERE sku LIKE '%.%'")).fetchall()
        print(f"Found {len(items_with_dots)} rows in order_items containing dots in SKU.")
        
        updated_items_count = 0
        for item in items_with_dots:
            item_id, item_sku = item
            clean_item_sku = item_sku.replace('.', '')
            print(f"Updating order_item ID {item_id}: '{item_sku}' -> '{clean_item_sku}'")
            session.execute(
                text("UPDATE order_items SET sku = :clean_sku, updated_at = NOW() WHERE id = :id"),
                {"clean_sku": clean_item_sku, "id": item_id}
            )
            updated_items_count += 1
            
        session.commit()
        print("\n" + "=" * 60)
        print("MIGRATION SUMMARY")
        print(f"Material Costs updated (SKU renamed): {updated_materials_count}")
        print(f"Material Costs merged (costs updated): {merged_materials_count}")
        print(f"Material Costs deleted (redundants):   {deleted_materials_count}")
        print(f"Order Items updated (SKU renamed):     {updated_items_count}")
        print("=" * 60)
        print("✅ Migration completed successfully!")
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ Error during migration execution: {e}")
        sys.exit(1)
    finally:
        session.close()

if __name__ == "__main__":
    main()
