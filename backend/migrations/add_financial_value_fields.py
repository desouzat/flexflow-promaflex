"""
FlexFlow - Database Migration: Add Financial Value Fields
Adds unit_value, item_total_value to order_items
Adds po_total_value to purchase_orders
Supports 22-field ONET structure with financial integrity
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from database import engine, SessionLocal

def run_migration():
    """Add financial value fields to support 22-field ONET structure"""
    
    print("=" * 80)
    print("FlexFlow - Adding Financial Value Fields Migration")
    print("=" * 80)
    
    with engine.connect() as conn:
        try:
            print("\n[1/3] Adding unit_value to order_items...")
            conn.execute(text("""
                ALTER TABLE order_items 
                ADD COLUMN IF NOT EXISTS unit_value NUMERIC(10, 2) NULL;
            """))
            conn.execute(text("""
                COMMENT ON COLUMN order_items.unit_value IS 
                'Unit value from ONET (Vl.Unit)';
            """))
            print("✓ unit_value column added")
            
            print("\n[2/3] Adding item_total_value to order_items...")
            conn.execute(text("""
                ALTER TABLE order_items 
                ADD COLUMN IF NOT EXISTS item_total_value NUMERIC(12, 2) NULL;
            """))
            conn.execute(text("""
                COMMENT ON COLUMN order_items.item_total_value IS 
                'Item total value from ONET (Total Item = Qtd × Vl.Unit)';
            """))
            print("✓ item_total_value column added")
            
            print("\n[3/3] Adding po_total_value to purchase_orders...")
            conn.execute(text("""
                ALTER TABLE purchase_orders 
                ADD COLUMN IF NOT EXISTS po_total_value NUMERIC(12, 2) NULL;
            """))
            conn.execute(text("""
                COMMENT ON COLUMN purchase_orders.po_total_value IS 
                'PO total value from ONET (Valor Total do Pedido)';
            """))
            print("✓ po_total_value column added")
            
            # Commit the transaction
            conn.commit()
            
            print("\n" + "=" * 80)
            print("✅ Migration completed successfully!")
            print("=" * 80)
            print("\nNew Fields Added:")
            print("  • order_items.unit_value (NUMERIC(10,2))")
            print("  • order_items.item_total_value (NUMERIC(12,2))")
            print("  • purchase_orders.po_total_value (NUMERIC(12,2))")
            print("\nThese fields support the 22-field ONET structure:")
            print("  • Vl.Unit (Unit Value)")
            print("  • Total Item (Quantity × Unit Value)")
            print("  • Valor Total do Pedido (Sum of all Total Items)")
            print("\n" + "=" * 80)
            
        except Exception as e:
            conn.rollback()
            print(f"\n❌ Migration failed: {str(e)}")
            raise

def verify_migration():
    """Verify that the migration was successful"""
    
    print("\n" + "=" * 80)
    print("Verifying Migration...")
    print("=" * 80)
    
    with engine.connect() as conn:
        # Check order_items columns
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'order_items'
            AND column_name IN ('unit_value', 'item_total_value')
            ORDER BY column_name;
        """))
        
        print("\n✓ order_items columns:")
        for row in result:
            print(f"  • {row[0]}: {row[1]} (nullable: {row[2]})")
        
        # Check purchase_orders columns
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'purchase_orders'
            AND column_name = 'po_total_value'
            ORDER BY column_name;
        """))
        
        print("\n✓ purchase_orders columns:")
        for row in result:
            print(f"  • {row[0]}: {row[1]} (nullable: {row[2]})")
    
    print("\n" + "=" * 80)
    print("✅ Verification complete!")
    print("=" * 80)

if __name__ == "__main__":
    try:
        run_migration()
        verify_migration()
        print("\n🎉 Financial value fields migration completed successfully!")
        print("You can now import ONET files with 22 fields including financial values.")
    except Exception as e:
        print(f"\n💥 Migration failed: {str(e)}")
        sys.exit(1)
