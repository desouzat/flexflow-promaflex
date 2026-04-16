"""
Migration: Add GlobalConfig table and Enums
Adds:
- GlobalConfig table for system parameters
- PackagingType and ProductionImpediment enums
- Default replacement_sla_multiplier config
"""

import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path.parent))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from backend.database import Base, SQLALCHEMY_DATABASE_URL, engine
from backend.models import GlobalConfig, Tenant
import uuid


def run_migration():
    """Execute migration to add GlobalConfig table"""
    
    SessionLocal = sessionmaker(bind=engine)
    
    print("[MIGRATION] Starting migration: add_global_config_and_enums")
    
    try:
        # Create all tables (will only create new ones)
        print("[MIGRATION] Creating GlobalConfig table...")
        Base.metadata.create_all(bind=engine, checkfirst=True)
        print("[SUCCESS] GlobalConfig table created successfully")
        
        # Add default configuration for all tenants
        session = SessionLocal()
        try:
            tenants = session.query(Tenant).all()
            print(f"[INFO] Found {len(tenants)} tenant(s)")
            
            for tenant in tenants:
                # Check if config already exists
                existing_config = session.query(GlobalConfig).filter(
                    GlobalConfig.tenant_id == tenant.id,
                    GlobalConfig.config_key == "replacement_sla_multiplier"
                ).first()
                
                if not existing_config:
                    # Create default replacement_sla_multiplier config
                    config = GlobalConfig(
                        id=uuid.uuid4(),
                        tenant_id=tenant.id,
                        config_key="replacement_sla_multiplier",
                        config_value="0.5",
                        config_type="float",
                        description="Multiplicador de SLA para pedidos de reposicao (0.5 = 50% do tempo normal)"
                    )
                    session.add(config)
                    print(f"[SUCCESS] Added replacement_sla_multiplier config for tenant {tenant.name}")
                else:
                    print(f"[SKIP] Config already exists for tenant {tenant.name}")
            
            session.commit()
            print("[SUCCESS] Default configurations added successfully")
            
        finally:
            session.close()
        
        print("[SUCCESS] Migration completed successfully!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
