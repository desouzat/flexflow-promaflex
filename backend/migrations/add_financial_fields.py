"""
Migration: Add Financial Fields
Adds manual_commission_rate to OrderItem and creates CommissionConfig table.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text, Column, String, Numeric, Boolean, DateTime, UUID, Integer, Index, CheckConstraint
from sqlalchemy.sql import func
from dotenv import load_dotenv
import uuid

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Get database URL
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://flexflow_app:Souza%40123@127.0.0.1:5434/flexflow_prod"
)


def upgrade():
    """Add financial fields to support Advanced Financial Module"""
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    with engine.connect() as conn:
        print("🔧 Starting financial fields migration...")
        
        # 1. Add manual_commission_rate to order_items
        print("📊 Adding manual_commission_rate to order_items...")
        try:
            conn.execute(text("""
                ALTER TABLE order_items
                ADD COLUMN IF NOT EXISTS manual_commission_rate NUMERIC(5, 2) NULL
                    COMMENT 'Manual commission rate override set by MASTER user (percentage)';
            """))
            conn.commit()
            print("✅ Added manual_commission_rate field")
        except Exception as e:
            print(f"⚠️  manual_commission_rate field may already exist: {e}")
        
        # 2. Add constraint to ensure manual_commission_rate is valid
        print("🔒 Adding constraint for manual_commission_rate...")
        try:
            conn.execute(text("""
                ALTER TABLE order_items
                ADD CONSTRAINT IF NOT EXISTS check_manual_commission_rate_range
                CHECK (manual_commission_rate IS NULL OR (manual_commission_rate >= 0 AND manual_commission_rate <= 100));
            """))
            conn.commit()
            print("✅ Added manual_commission_rate constraint")
        except Exception as e:
            print(f"⚠️  Constraint may already exist: {e}")
        
        # 3. Create commission_config table for editable commission ladder
        print("📋 Creating commission_config table...")
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS commission_config (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    min_margin NUMERIC(5, 2) NOT NULL,
                    max_margin NUMERIC(5, 2) NOT NULL,
                    commission_rate NUMERIC(5, 2) NOT NULL,
                    has_alert BOOLEAN DEFAULT FALSE,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
                    CONSTRAINT check_margin_range CHECK (min_margin >= 0 AND max_margin <= 999.99),
                    CONSTRAINT check_margin_order CHECK (min_margin <= max_margin),
                    CONSTRAINT check_commission_range CHECK (commission_rate >= 0 AND commission_rate <= 100)
                );
            """))
            conn.commit()
            print("✅ Created commission_config table")
        except Exception as e:
            print(f"⚠️  commission_config table may already exist: {e}")
        
        # 4. Create indexes for commission_config
        print("🔍 Creating indexes for commission_config...")
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_commission_config_tenant_id ON commission_config(tenant_id);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_commission_config_active ON commission_config(is_active);
            """))
            conn.commit()
            print("✅ Created commission_config indexes")
        except Exception as e:
            print(f"⚠️  Indexes may already exist: {e}")
        
        # 5. Create vp_rates_config table for editable VP rates
        print("💰 Creating vp_rates_config table...")
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS vp_rates_config (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
                    term_days INTEGER NOT NULL,
                    rate NUMERIC(6, 4) NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
                    CONSTRAINT check_term_days_positive CHECK (term_days > 0),
                    CONSTRAINT check_vp_rate_range CHECK (rate >= 0 AND rate <= 1),
                    CONSTRAINT unique_tenant_term UNIQUE (tenant_id, term_days)
                );
            """))
            conn.commit()
            print("✅ Created vp_rates_config table")
        except Exception as e:
            print(f"⚠️  vp_rates_config table may already exist: {e}")
        
        # 6. Create indexes for vp_rates_config
        print("🔍 Creating indexes for vp_rates_config...")
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_vp_rates_config_tenant_id ON vp_rates_config(tenant_id);
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_vp_rates_config_term ON vp_rates_config(term_days);
            """))
            conn.commit()
            print("✅ Created vp_rates_config indexes")
        except Exception as e:
            print(f"⚠️  Indexes may already exist: {e}")
        
        # 7. Seed default commission ladder (if table is empty)
        print("🌱 Seeding default commission ladder...")
        try:
            # Check if we need to seed
            result = conn.execute(text("SELECT COUNT(*) FROM commission_config"))
            count = result.scalar()
            
            if count == 0:
                # Get first tenant for seeding
                result = conn.execute(text("SELECT id FROM tenants LIMIT 1"))
                tenant_row = result.fetchone()
                
                if tenant_row:
                    tenant_id = tenant_row[0]
                    
                    # Insert default ladder
                    default_ladder = [
                        (0.00, 18.99, 0.00, True, 1),
                        (19.00, 24.99, 2.00, False, 2),
                        (25.00, 29.99, 2.25, False, 3),
                        (30.00, 39.99, 2.50, False, 4),
                        (40.00, 44.99, 3.50, False, 5),
                        (45.00, 49.99, 4.00, False, 6),
                        (50.00, 999.99, 4.50, False, 7),
                    ]
                    
                    for min_m, max_m, comm, alert, order in default_ladder:
                        conn.execute(text("""
                            INSERT INTO commission_config 
                            (tenant_id, min_margin, max_margin, commission_rate, has_alert, display_order)
                            VALUES (:tenant_id, :min_margin, :max_margin, :commission_rate, :has_alert, :display_order)
                        """), {
                            "tenant_id": tenant_id,
                            "min_margin": min_m,
                            "max_margin": max_m,
                            "commission_rate": comm,
                            "has_alert": alert,
                            "display_order": order
                        })
                    
                    conn.commit()
                    print("✅ Seeded default commission ladder")
                else:
                    print("⚠️  No tenants found, skipping seed")
            else:
                print("ℹ️  Commission config already has data, skipping seed")
        except Exception as e:
            print(f"⚠️  Error seeding commission ladder: {e}")
        
        # 8. Seed default VP rates (if table is empty)
        print("🌱 Seeding default VP rates...")
        try:
            result = conn.execute(text("SELECT COUNT(*) FROM vp_rates_config"))
            count = result.scalar()
            
            if count == 0:
                result = conn.execute(text("SELECT id FROM tenants LIMIT 1"))
                tenant_row = result.fetchone()
                
                if tenant_row:
                    tenant_id = tenant_row[0]
                    
                    default_rates = [
                        (30, 0.0150),
                        (60, 0.0300),
                        (90, 0.0450),
                        (120, 0.0600),
                    ]
                    
                    for term, rate in default_rates:
                        conn.execute(text("""
                            INSERT INTO vp_rates_config 
                            (tenant_id, term_days, rate)
                            VALUES (:tenant_id, :term_days, :rate)
                        """), {
                            "tenant_id": tenant_id,
                            "term_days": term,
                            "rate": rate
                        })
                    
                    conn.commit()
                    print("✅ Seeded default VP rates")
                else:
                    print("⚠️  No tenants found, skipping seed")
            else:
                print("ℹ️  VP rates config already has data, skipping seed")
        except Exception as e:
            print(f"⚠️  Error seeding VP rates: {e}")
        
        print("✅ Financial fields migration completed successfully!")


def downgrade():
    """Remove financial fields"""
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    
    with engine.connect() as conn:
        print("🔧 Rolling back financial fields migration...")
        
        # Drop tables
        conn.execute(text("DROP TABLE IF EXISTS vp_rates_config CASCADE;"))
        conn.execute(text("DROP TABLE IF EXISTS commission_config CASCADE;"))
        
        # Remove column
        conn.execute(text("ALTER TABLE order_items DROP COLUMN IF EXISTS manual_commission_rate;"))
        
        conn.commit()
        print("✅ Rollback completed")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "downgrade":
        downgrade()
    else:
        upgrade()
