import os
import sys
import asyncio
from pathlib import Path

# Add project root directory to path to import backend modules
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir.parent))

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

# Set up utf-8 encoding for stdout/stderr in Windows terminal
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

from backend.database import SessionLocal
from backend.models import User, Tenant
from backend.routers.auth import get_password_hash, verify_password
from backend.schemas.auth_schema import UserInfo
from backend.routers.dashboard_router import get_celso_kpis

async def verify_matrix():
    print("=" * 70)
    print("ACCESS MATRIX SECURITY VERIFICATION HARNESS")
    print("=" * 70)
    
    db = SessionLocal()
    try:
        # 1. Ensure a default tenant exists
        tenant = db.query(Tenant).filter(Tenant.name == "PromaFlex").first()
        if not tenant:
            tenant = Tenant(name="PromaFlex", cnpj="12.345.678/0001-90", is_active=True)
            db.add(tenant)
            db.flush()
            
        # 2. Ensure test users exist with correct roles
        # - admin user (needs to be created/seeded)
        admin_email = "admin_matrix@promaflex.com.br"
        admin_user = db.query(User).filter(User.email == admin_email).first()
        if not admin_user:
            admin_user = User(
                tenant_id=tenant.id,
                name="Admin Matrix Test",
                email=admin_email,
                hashed_password=get_password_hash("Proma@2026"),
                role="admin",
                area="Management",
                is_active=True
            )
            db.add(admin_user)
            db.flush()
            
        # - master user (e.g., alex@promaflex.com.br or anderson.moreno@promaflex.com.br)
        master_email = "anderson.moreno@promaflex.com.br"
        master_user = db.query(User).filter(User.email == master_email).first()
        if not master_user:
            master_user = User(
                tenant_id=tenant.id,
                name="Anderson Moreno",
                email=master_email,
                hashed_password=get_password_hash("Proma@2026"),
                role="master",
                area="Financeiro",
                is_active=True
            )
            db.add(master_user)
            db.flush()
            
        # - operator user (e.g., mairla@promaflex.com.br)
        operator_email = "mairla@promaflex.com.br"
        operator_user = db.query(User).filter(User.email == operator_email).first()
        if not operator_user:
            operator_user = User(
                tenant_id=tenant.id,
                name="Mairla",
                email=operator_email,
                hashed_password=get_password_hash("Proma@2026"),
                role="operator",
                area="Comercial",
                is_active=True
            )
            db.add(operator_user)
            db.flush()
            
        db.commit()
        
        # 3. Simulate requests for each user and verify masking behavior
        
        # --- Role 1: Admin ---
        admin_info = UserInfo(
            id=str(admin_user.id),
            tenant_id=str(admin_user.tenant_id),
            email=admin_user.email,
            name=admin_user.name,
            role=admin_user.role,
            permissions=[],
            is_active=admin_user.is_active
        )
        admin_kpis = await get_celso_kpis(current_user=admin_info, db=db)
        admin_margins = admin_kpis.get("margin_by_unit", {})
        
        admin_view_ok = True
        for unit, details in admin_margins.items():
            if details.get("total_margin") == "***" or details.get("margin_percentage") == "***":
                admin_view_ok = False
                
        if admin_view_ok:
            print("Admin: View OK.")
        else:
            print("Admin: FAILED (margins were masked)")
            
        # --- Role 2: Master ---
        master_info = UserInfo(
            id=str(master_user.id),
            tenant_id=str(master_user.tenant_id),
            email=master_user.email,
            name=master_user.name,
            role=master_user.role,
            permissions=[],
            is_active=master_user.is_active
        )
        master_kpis = await get_celso_kpis(current_user=master_info, db=db)
        master_margins = master_kpis.get("margin_by_unit", {})
        
        master_view_ok = True
        for unit, details in master_margins.items():
            if details.get("total_margin") == "***" or details.get("margin_percentage") == "***":
                master_view_ok = False
                
        if master_view_ok:
            print("Master: View OK.")
        else:
            print("Master: FAILED (margins were masked)")
            
        # --- Role 3: Operator ---
        operator_info = UserInfo(
            id=str(operator_user.id),
            tenant_id=str(operator_user.tenant_id),
            email=operator_user.email,
            name=operator_user.name,
            role=operator_user.role,
            permissions=[],
            is_active=operator_user.is_active
        )
        operator_kpis = await get_celso_kpis(current_user=operator_info, db=db)
        operator_margins = operator_kpis.get("margin_by_unit", {})
        
        operator_masked_ok = True
        for unit, details in operator_margins.items():
            if details.get("total_margin") != "***" or details.get("margin_percentage") != "***":
                operator_masked_ok = False
                
        if operator_masked_ok:
            print("Operator: Masked OK.")
        else:
            print("Operator: FAILED (margins were not masked)")
            
        print("=" * 70)
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(verify_matrix())
