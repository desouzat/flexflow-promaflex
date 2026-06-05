import os
import sys
import asyncio
from pathlib import Path

# Add project root directory to path to import backend modules
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir.parent))

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

from backend.database import SessionLocal
from backend.models import User
from backend.routers.auth import verify_password, SECURITY_PEPPER
from backend.schemas.auth_schema import UserInfo
from backend.routers.dashboard_router import get_celso_kpis

# List of 16 official users to verify login for
OFFICIAL_USERS = [
    "mairla@promaflex.com.br",
    "jader@promaflex.com.br",
    "mvelletri_promaflex@grupovelletri.com.br",
    "barbara@bardge.com.br",
    "anderson.moreno@promaflex.com.br",
    "alex@promaflex.com.br",
    "cristiane.oliveira@promaflex.com.br",
    "fabio_promaflex@grupovelletri.com.br",
    "gabriel_promaflex@grupovelletri.com.br",
    "expedicao@promaflex.com.br",
    "jonata_promaflex@grupovelletri.com.br",
    "cristiano_promaflex@grupovelletri.com.br",
    "rogerio_promaflex@grupovelletri.com.br",
    "claudio.xavier@grupovelletri.com.br",
    "embalagem_promaflex@grupovelletri.com.br",
    "andrea@grupovelletri.com.br"
]

DEFAULT_PASSWORD = "Proma@2026"

async def run_prod_readiness_checks_async():
    print("=" * 70)
    print("PRODUCTION READINESS VERIFICATION HARNESS (H-04)")
    print("=" * 70)
    
    # ─── Check 1: SECURITY_PEPPER ─────────────────────────────────────────────
    print("Check 1: Verification of SECURITY_PEPPER loading...")
    if not SECURITY_PEPPER:
        print("❌ FAILED: SECURITY_PEPPER is empty or not loaded from .env")
        return 1
        
    print(f"   [OK] SECURITY_PEPPER loaded from .env (Length: {len(SECURITY_PEPPER)} characters)")
    if len(SECURITY_PEPPER) < 32:
        print(f"⚠️  WARNING: SECURITY_PEPPER length is {len(SECURITY_PEPPER)}, expected at least 32")
    
    db = SessionLocal()
    
    try:
        # ─── Check 2: Official Logins ─────────────────────────────────────────────
        print("\nCheck 2: Verification of login for all 16 official users...")
        all_logins_ok = True
        user_objects = {}
        
        for idx, email in enumerate(OFFICIAL_USERS, 1):
            user = db.query(User).filter(User.email == email).first()
            if not user:
                print(f"   [{idx:02d}/16] ❌ LOGIN FAILED: User not found in DB: {email}")
                all_logins_ok = False
                continue
                
            # Verify password
            is_valid = verify_password(DEFAULT_PASSWORD, user.hashed_password)
            if is_valid and user.is_active:
                user_objects[email] = user
                print(f"   [{idx:02d}/16] Login successful for: {email} (role: {user.role}, area: {user.area})")
            else:
                print(f"   [{idx:02d}/16] ❌ LOGIN FAILED: Invalid credentials/inactive for: {email}")
                all_logins_ok = False
                
        if not all_logins_ok:
            print("\n❌ FAILED: One or more official users failed to authenticate.")
            return 1
        print("   [OK] All 16 official users authenticated successfully.")

        # ─── Check 3: Operator Dashboard Margin Masking ───────────────────────────
        print("\nCheck 3: Dashboard Margin Masking for non-privileged user (Comercial)...")
        operator_email = "mairla@promaflex.com.br" # Comercial operator
        operator = user_objects.get(operator_email)
        
        operator_info = UserInfo(
            id=str(operator.id),
            tenant_id=str(operator.tenant_id),
            email=operator.email,
            name=operator.name,
            role=operator.role,
            permissions=[],
            is_active=operator.is_active
        )
        
        kpis = await get_celso_kpis(current_user=operator_info, db=db)
        margins = kpis.get("margin_by_unit", {})
        
        # Assert margins are masked with '***'
        masking_success = True
        print("   Verifying margin fields inside response:")
        for unit, details in margins.items():
            total_margin = details.get("total_margin")
            margin_pct = details.get("margin_percentage")
            
            print(f"      - {unit}: total_margin={total_margin!r}, margin_percentage={margin_pct!r}")
            
            if total_margin != "***" or margin_pct != "***":
                print(f"      ❌ ERROR: Margin for unit {unit} is NOT masked! (Found values: total_margin={total_margin}, pct={margin_pct})")
                masking_success = False
                
        if not masking_success:
            print("❌ FAILED: Operator dashboard margins are NOT correctly masked.")
            return 1
            
        print("   [OK] Margin Masking is active and correctly returning '***' for all units.")

        # ─── Check 4: Privileged Dashboard Margin Unmasking ───────────────────────
        print("\nCheck 4: Dashboard Margin Unmasking for privileged user (Financeiro Master)...")
        master_email = "anderson.moreno@promaflex.com.br" # Master
        master = user_objects.get(master_email)
        
        master_info = UserInfo(
            id=str(master.id),
            tenant_id=str(master.tenant_id),
            email=master.email,
            name=master.name,
            role=master.role,
            permissions=[],
            is_active=master.is_active
        )
        
        kpis = await get_celso_kpis(current_user=master_info, db=db)
        margins = kpis.get("margin_by_unit", {})
        
        unmasking_success = True
        print("   Verifying margin fields inside response:")
        for unit, details in margins.items():
            total_margin = details.get("total_margin")
            margin_pct = details.get("margin_percentage")
            
            print(f"      - {unit}: total_margin={total_margin!r}, margin_percentage={margin_pct!r}")
            
            if total_margin == "***" or margin_pct == "***":
                print(f"      ❌ ERROR: Margin for unit {unit} is masked for privileged master user!")
                unmasking_success = False
                
        if not unmasking_success:
            print("❌ FAILED: Master user is incorrectly receiving masked values.")
            return 1
            
        print("   [OK] Unmasked margins retrieved successfully by master user.")
        
        print("\n" + "=" * 70)
        print("🎉 SUCCESS: ALL PRODUCTION READINESS CHECKS PASSED!")
        print("=" * 70)
        return 0
    finally:
        db.close()

def main():
    loop = asyncio.get_event_loop()
    sys.exit(loop.run_until_complete(run_prod_readiness_checks_async()))

if __name__ == "__main__":
    main()
