"""
Migration Script: Add Partition Feature
Adds support for PO partitioning between PCP and Commercial roles.

Features:
- New status: WAITING_COMMERCIAL_PARTITION
- Partition relationship fields (parent_po_id, partition_reason)
- Shipping cost field for partition recalculation
- Enhanced audit log for partition traceability
"""

from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from pathlib import Path
import os
import sys

# Load environment variables
current_dir = Path(__file__).resolve().parent.parent
env_path = current_dir / '.env'
load_dotenv(dotenv_path=env_path)

# Get database URL
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://flexflow_app:Souza%40123@127.0.0.1:5433/flexflow_prod"
)


def run_migration():
    """Execute the migration"""
    
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    print(">> Iniciando migracao de Particao de PO...")
    
    with engine.connect() as conn:
        try:
            # 1. Add partition-related fields to purchase_orders
            print("1. Adicionando campos de particao a tabela purchase_orders...")
            
            # Parent PO reference for child POs
            conn.execute(text("""
                ALTER TABLE purchase_orders 
                ADD COLUMN IF NOT EXISTS parent_po_id UUID REFERENCES purchase_orders(id) ON DELETE SET NULL;
            """))
            
            # Partition reason (stored when PCP suggests partition)
            conn.execute(text("""
                ALTER TABLE purchase_orders 
                ADD COLUMN IF NOT EXISTS partition_reason TEXT;
            """))
            
            # Shipping cost for partition recalculation
            conn.execute(text("""
                ALTER TABLE purchase_orders 
                ADD COLUMN IF NOT EXISTS shipping_cost NUMERIC(10, 2) DEFAULT 0.00;
            """))
            
            # Flag to identify if this is a partitioned PO
            conn.execute(text("""
                ALTER TABLE purchase_orders 
                ADD COLUMN IF NOT EXISTS is_partitioned BOOLEAN DEFAULT FALSE NOT NULL;
            """))
            
            # Partition metadata (stores partition history and calculations)
            conn.execute(text("""
                ALTER TABLE purchase_orders 
                ADD COLUMN IF NOT EXISTS partition_metadata JSONB;
            """))
            
            conn.commit()
            print("   OK - Campos de particao adicionados")
            
            # 2. Create indexes for partition queries
            print("2. Criando indices para consultas de particao...")
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_po_parent_po_id 
                ON purchase_orders(parent_po_id);
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_po_is_partitioned 
                ON purchase_orders(is_partitioned);
            """))
            
            conn.commit()
            print("   OK - Indices criados")
            
            # 3. Add partition tracking to order_items
            print("3. Adicionando rastreamento de particao aos itens...")
            
            # Track which partition this item belongs to
            conn.execute(text("""
                ALTER TABLE order_items 
                ADD COLUMN IF NOT EXISTS partition_group VARCHAR(50);
            """))
            
            # Original item reference (for child items to reference mother item)
            conn.execute(text("""
                ALTER TABLE order_items 
                ADD COLUMN IF NOT EXISTS original_item_id UUID REFERENCES order_items(id) ON DELETE SET NULL;
            """))
            
            conn.commit()
            print("   OK - Rastreamento de particao adicionado aos itens")
            
            # 4. Add partition action type to audit logs
            print("4. Adicionando suporte a particao no audit log...")
            
            # Add partition-specific fields to extra_data tracking
            conn.execute(text("""
                COMMENT ON COLUMN audit_logs.extra_data IS 
                'Additional data including partition info: mother_po_id, child_po_id, partition_type, items_split';
            """))
            
            conn.commit()
            print("   OK - Suporte a particao adicionado ao audit log")
            
            # 5. Update status constraint to include new partition status
            print("5. Atualizando constraint de status para incluir WAITING_COMMERCIAL_PARTITION...")
            
            # Drop old constraint
            conn.execute(text("""
                ALTER TABLE purchase_orders 
                DROP CONSTRAINT IF EXISTS check_po_status_macro;
            """))
            
            # Add new constraint with partition status
            conn.execute(text("""
                ALTER TABLE purchase_orders 
                ADD CONSTRAINT check_po_status_macro 
                CHECK (status_macro IN (
                    'DRAFT', 
                    'SUBMITTED', 
                    'APPROVED', 
                    'IN_PROGRESS', 
                    'COMPLETED', 
                    'CANCELLED',
                    'WAITING_COMMERCIAL_PARTITION'
                ));
            """))
            
            conn.commit()
            print("   OK - Constraint de status atualizado")
            
            # 6. Create view for partition relationships
            print("6. Criando view para relacionamentos de particao...")
            
            conn.execute(text("""
                CREATE OR REPLACE VIEW partition_relationships AS
                SELECT 
                    mother.id as mother_po_id,
                    mother.po_number as mother_po_number,
                    mother.status_macro as mother_status,
                    child.id as child_po_id,
                    child.po_number as child_po_number,
                    child.status_macro as child_status,
                    child.partition_reason,
                    child.created_at as partition_date,
                    mother.tenant_id
                FROM purchase_orders mother
                LEFT JOIN purchase_orders child ON child.parent_po_id = mother.id
                WHERE mother.is_partitioned = TRUE OR child.parent_po_id IS NOT NULL;
            """))
            
            conn.commit()
            print("   OK - View de relacionamentos criada")
            
            print("\n>> Migracao de Particao concluida com sucesso!")
            print("\nResumo das alteracoes:")
            print("   - Novo status: WAITING_COMMERCIAL_PARTITION")
            print("   - Campos de particao adicionados a purchase_orders")
            print("   - Rastreamento de particao adicionado a order_items")
            print("   - Indices otimizados para consultas de particao")
            print("   - View para visualizacao de relacionamentos mae/filho")
            
            return True
            
        except Exception as e:
            print(f"\n!! Erro durante a migracao: {str(e)}")
            conn.rollback()
            return False


def rollback_migration():
    """Rollback the migration"""
    
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    print(">> Revertendo migracao de Particao...")
    
    with engine.connect() as conn:
        try:
            # Drop view
            print("1. Removendo view de relacionamentos...")
            conn.execute(text("DROP VIEW IF EXISTS partition_relationships CASCADE;"))
            conn.commit()
            print("   OK - View removida")
            
            # Restore old status constraint
            print("2. Restaurando constraint de status original...")
            conn.execute(text("""
                ALTER TABLE purchase_orders 
                DROP CONSTRAINT IF EXISTS check_po_status_macro;
            """))
            conn.execute(text("""
                ALTER TABLE purchase_orders 
                ADD CONSTRAINT check_po_status_macro 
                CHECK (status_macro IN (
                    'DRAFT', 
                    'SUBMITTED', 
                    'APPROVED', 
                    'IN_PROGRESS', 
                    'COMPLETED', 
                    'CANCELLED'
                ));
            """))
            conn.commit()
            print("   OK - Constraint restaurado")
            
            # Remove fields from order_items
            print("3. Removendo campos de particao de order_items...")
            conn.execute(text("ALTER TABLE order_items DROP COLUMN IF EXISTS partition_group;"))
            conn.execute(text("ALTER TABLE order_items DROP COLUMN IF EXISTS original_item_id;"))
            conn.commit()
            print("   OK - Campos removidos de order_items")
            
            # Remove fields from purchase_orders
            print("4. Removendo campos de particao de purchase_orders...")
            conn.execute(text("ALTER TABLE purchase_orders DROP COLUMN IF EXISTS parent_po_id;"))
            conn.execute(text("ALTER TABLE purchase_orders DROP COLUMN IF EXISTS partition_reason;"))
            conn.execute(text("ALTER TABLE purchase_orders DROP COLUMN IF EXISTS shipping_cost;"))
            conn.execute(text("ALTER TABLE purchase_orders DROP COLUMN IF EXISTS is_partitioned;"))
            conn.execute(text("ALTER TABLE purchase_orders DROP COLUMN IF EXISTS partition_metadata;"))
            conn.commit()
            print("   OK - Campos removidos de purchase_orders")
            
            print("\n>> Rollback concluido com sucesso!")
            return True
            
        except Exception as e:
            print(f"\n!! Erro durante o rollback: {str(e)}")
            conn.rollback()
            return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        success = rollback_migration()
    else:
        success = run_migration()
    
    sys.exit(0 if success else 1)
