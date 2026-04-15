"""
Migration Script: Add Material Costs Table and Enhanced Audit Features
Adds:
- material_costs table
- extra_metadata JSONB field to order_items
- is_exception and justification fields to audit_logs
"""

from sqlalchemy import create_engine, text
from backend.database import SQLALCHEMY_DATABASE_URL
import sys


def run_migration():
    """Execute the migration"""
    
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    print("🔄 Iniciando migração do banco de dados...")
    
    with engine.connect() as conn:
        try:
            # 1. Add extra_metadata to order_items
            print("1️⃣ Adicionando campo extra_metadata à tabela order_items...")
            conn.execute(text("""
                ALTER TABLE order_items 
                ADD COLUMN IF NOT EXISTS extra_metadata JSONB;
            """))
            conn.commit()
            print("   ✅ Campo extra_metadata adicionado")
            
            # 2. Add is_exception and justification to audit_logs
            print("2️⃣ Adicionando campos is_exception e justification à tabela audit_logs...")
            conn.execute(text("""
                ALTER TABLE audit_logs 
                ADD COLUMN IF NOT EXISTS is_exception BOOLEAN DEFAULT FALSE NOT NULL;
            """))
            conn.execute(text("""
                ALTER TABLE audit_logs 
                ADD COLUMN IF NOT EXISTS justification TEXT;
            """))
            conn.commit()
            print("   ✅ Campos is_exception e justification adicionados")
            
            # 3. Create index on is_exception
            print("3️⃣ Criando índice em audit_logs.is_exception...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_audit_is_exception 
                ON audit_logs(is_exception);
            """))
            conn.commit()
            print("   ✅ Índice criado")
            
            # 4. Create material_costs table
            print("4️⃣ Criando tabela material_costs...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS material_costs (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    sku VARCHAR(100) NOT NULL,
                    nome VARCHAR(255) NOT NULL,
                    custo_mp_kg NUMERIC(10, 2) NOT NULL CHECK (custo_mp_kg >= 0),
                    rendimento NUMERIC(10, 4) NOT NULL CHECK (rendimento > 0),
                    indice_impostos NUMERIC(5, 2) NOT NULL DEFAULT 22.25 
                        CHECK (indice_impostos >= 0 AND indice_impostos <= 100),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
                    CONSTRAINT unique_tenant_sku UNIQUE (tenant_id, sku)
                );
            """))
            conn.commit()
            print("   ✅ Tabela material_costs criada")
            
            # 5. Create indexes on material_costs
            print("5️⃣ Criando índices em material_costs...")
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_material_cost_tenant_id 
                ON material_costs(tenant_id);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_material_cost_sku 
                ON material_costs(sku);
            """))
            conn.commit()
            print("   ✅ Índices criados")
            
            # 6. Add comment to material_costs columns
            print("6️⃣ Adicionando comentários às colunas...")
            conn.execute(text("""
                COMMENT ON COLUMN material_costs.custo_mp_kg IS 
                'Custo de matéria-prima por kg';
            """))
            conn.execute(text("""
                COMMENT ON COLUMN material_costs.rendimento IS 
                'Rendimento em kg por unidade';
            """))
            conn.execute(text("""
                COMMENT ON COLUMN material_costs.indice_impostos IS 
                'Índice de impostos em percentual (padrão 22.25%)';
            """))
            conn.commit()
            print("   ✅ Comentários adicionados")
            
            print("\n✅ Migração concluída com sucesso!")
            return True
            
        except Exception as e:
            print(f"\n❌ Erro durante a migração: {str(e)}")
            conn.rollback()
            return False


def rollback_migration():
    """Rollback the migration"""
    
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    print("🔄 Revertendo migração do banco de dados...")
    
    with engine.connect() as conn:
        try:
            # Remove material_costs table
            print("1️⃣ Removendo tabela material_costs...")
            conn.execute(text("DROP TABLE IF EXISTS material_costs CASCADE;"))
            conn.commit()
            print("   ✅ Tabela removida")
            
            # Remove fields from audit_logs
            print("2️⃣ Removendo campos de audit_logs...")
            conn.execute(text("ALTER TABLE audit_logs DROP COLUMN IF EXISTS is_exception;"))
            conn.execute(text("ALTER TABLE audit_logs DROP COLUMN IF EXISTS justification;"))
            conn.commit()
            print("   ✅ Campos removidos")
            
            # Remove extra_metadata from order_items
            print("3️⃣ Removendo campo extra_metadata de order_items...")
            conn.execute(text("ALTER TABLE order_items DROP COLUMN IF EXISTS extra_metadata;"))
            conn.commit()
            print("   ✅ Campo removido")
            
            print("\n✅ Rollback concluído com sucesso!")
            return True
            
        except Exception as e:
            print(f"\n❌ Erro durante o rollback: {str(e)}")
            conn.rollback()
            return False


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        success = rollback_migration()
    else:
        success = run_migration()
    
    sys.exit(0 if success else 1)
