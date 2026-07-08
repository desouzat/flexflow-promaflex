import sys
import os
from datetime import datetime

# Fix encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add project root directory to path to import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.orm import Session
from backend.database import SessionLocal, engine, Base
from backend.models import Tenant, User
from backend.routers.auth import get_password_hash

# ── OFFICIAL PRODUCTION USER LIST — 23 accounts (Andrea's final list, 2026-07-07) ──────────────
OFFICIAL_USERS = [
    # ── MASTER ROLES ──────────────────────────────────────────────────────────────────────────────
    {"area": "Management",  "email": "andrea@promaflex.com.br",                     "role": "master",   "name": "Andrea"},
    {"area": "Management",  "email": "celso.paes@promaflex.com.br",                 "role": "master",   "name": "Celso Paes"},

    # ── COMERCIAL CONFERÊNCIA (Mesa de Conferência operators) ─────────────────────────────────────
    {"area": "Comercial",   "email": "mairla@promaflex.com.br",                     "role": "operator", "name": "Mairla"},
    {"area": "Comercial",   "email": "abimaelbrito@promaflex.com.br",               "role": "operator", "name": "Abimael Brito"},
    {"area": "Comercial",   "email": "comercial@promaflex.com.br",                  "role": "operator", "name": "Comercial Promaflex"},

    # ── COMERCIAL OPERATORS ────────────────────────────────────────────────────────────────────────
    {"area": "Comercial",   "email": "jader@promaflex.com.br",                      "role": "operator", "name": "Jader"},
    {"area": "Comercial",   "email": "mvelletri_promaflex@grupovelletri.com.br",    "role": "operator", "name": "Mvelletri Promaflex"},
    {"area": "Comercial",   "email": "barbara@bardge.com.br",                       "role": "operator", "name": "Barbara"},
    {"area": "Comercial",   "email": "alexandre@promaflex.com.br",                  "role": "operator", "name": "Alexandre"},
    {"area": "Comercial",   "email": "leandro@promaflex.com.br",                    "role": "operator", "name": "Leandro"},
    {"area": "Comercial",   "email": "clayton@promaflex.com.br",                    "role": "operator", "name": "Clayton"},
    {"area": "Comercial",   "email": "fabio.sodre@promaflex.com.br",                "role": "operator", "name": "Fabio Sodre"},
    {"area": "Comercial",   "email": "Luis.monteiro@promaflex.com.br",              "role": "operator", "name": "Luis Monteiro"},
    {"area": "Comercial",   "email": "isadora_promaflex@grupovelletri.com.br",      "role": "operator", "name": "Isadora Promaflex"},
    {"area": "Comercial",   "email": "guilherme@promaflex.com.br",                  "role": "operator", "name": "Guilherme"},
    {"area": "Comercial",   "email": "psauma_promaflex@grupovelletri.com.br",       "role": "operator", "name": "Psauma Promaflex"},
    {"area": "Comercial",   "email": "rodrigo.cruz@promaflex.com.br",               "role": "operator", "name": "Rodrigo Cruz"},

    # ── LOGISTICA & EXPEDICAO ──────────────────────────────────────────────────────────────────────
    {"area": "Expedicao",   "email": "roberto.souza@promaflex.com.br",              "role": "operator", "name": "Roberto Souza"},
    {"area": "Expedicao",   "email": "gabriel_promaflex@grupovelletri.com.br",      "role": "operator", "name": "Gabriel Promaflex"},
    {"area": "Expedicao",   "email": "Expedicao@promaflex.com.br",                  "role": "operator", "name": "Expedicao Promaflex"},
    {"area": "Expedicao",   "email": "luis.silva@promaflex.com.br",                 "role": "operator", "name": "Luis Silva"},

    # ── PCP OPERATORS ─────────────────────────────────────────────────────────────────────────────
    # Note: Jonata also covers Embalagem area per Andrea's request
    {"area": "PCP",         "email": "Jonata_promaflex@grupovelletri.com.br",       "role": "operator", "name": "Jonata Promaflex"},
    {"area": "PCP",         "email": "cristiano_promaflex@grupovelletri.com.br",    "role": "operator", "name": "Cristiano Promaflex"},
    {"area": "PCP",         "email": "rogerio_promaflex@grupovelletri.com.br",      "role": "operator", "name": "Rogerio Promaflex"},
    {"area": "PCP",         "email": "claudio.xavier@grupovelletri.com.br",         "role": "operator", "name": "Claudio Xavier"},

    # ── EMBALAGEM OPERATOR ─────────────────────────────────────────────────────────────────────────
    {"area": "Embalagem",   "email": "Embalagem_promaflex@grupovelletri.com.br",    "role": "operator", "name": "Embalagem Promaflex"},

    # ── CRITICAL: Primary admin account — must ALWAYS remain present and active ───────────────────
    {"area": "Management",  "email": "thiago@botcase.net",                          "role": "admin",    "name": "Thiago BotCase",
     "is_sla_manager": True},
]


DEFAULT_PASSWORD = "Proma@2026"

def seed_users():
    db: Session = SessionLocal()
    try:
        print("=" * 60)
        print("OFFICIAL USER SEEDING SCRIPT (Task 2)")
        print("=" * 60)
        
        # 1. Find or create default tenant
        tenant_name = "PromaFlex"
        tenant_cnpj = "12.345.678/0001-90"
        
        tenant = db.query(Tenant).filter(Tenant.name == tenant_name).first()
        if not tenant:
            tenant = db.query(Tenant).filter(Tenant.cnpj == tenant_cnpj).first()
            
        if not tenant:
            print(f"Creating tenant '{tenant_name}'...")
            tenant = Tenant(
                name=tenant_name,
                cnpj=tenant_cnpj,
                is_active=True
            )
            db.add(tenant)
            db.flush()
            print(f"Tenant created with ID: {tenant.id}")
        else:
            tenant.name = tenant_name
            db.add(tenant)
            db.flush()
            print(f"Using existing tenant: '{tenant.name}' (ID: {tenant.id})")
            
        # 2. Hash default password
        print("Generating password hash with pepper...")
        hashed_pwd = get_password_hash(DEFAULT_PASSWORD)
        
        # 3. Seed users
        total = len(OFFICIAL_USERS)
        processed_count = 0
        for user_info in OFFICIAL_USERS:
            email           = user_info["email"]
            role            = user_info["role"]
            area            = user_info["area"]
            name            = user_info["name"]
            is_sla_manager  = user_info.get("is_sla_manager", False)

            # Check if user exists by email (case-insensitive)
            existing_user = db.query(User).filter(
                User.email.ilike(email)
            ).first()

            if existing_user:
                print(f"User {email} already exists. Updating area='{area}', role='{role}'...")
                existing_user.name            = name
                existing_user.area            = area
                existing_user.role            = role
                existing_user.hashed_password = hashed_pwd
                existing_user.is_active       = True
                if is_sla_manager:
                    existing_user.is_sla_manager = True
                db.add(existing_user)
                status_str = "UPDATED"
            else:
                print(f"Creating new user {email} (area='{area}', role='{role}')...")
                new_user = User(
                    tenant_id=tenant.id,
                    name=name,
                    email=email,
                    hashed_password=hashed_pwd,
                    role=role,
                    area=area,
                    is_active=True,
                    is_sla_manager=is_sla_manager,
                )
                db.add(new_user)
                status_str = "CREATED"

            processed_count += 1
            print(f"  [{processed_count:02d}/{total}] {email} -> {status_str}")

        db.commit()
        print("=" * 60)
        print(f"SUCCESS: Seeding completed! {processed_count}/{total} users processed.")
        print("=" * 60)

        # ── Verification: count active users in DB ─────────────────────────────
        active_users = db.query(User).filter(
            User.tenant_id == tenant.id,
            User.is_active == True
        ).order_by(User.area, User.email).all()

        print(f"\nVERIFICATION: Total active users in flexflow_prod = {len(active_users)}")
        print("-" * 72)
        print(f"  {'#':<4} {'Email':<48} {'Role':<10} {'Area'}")
        print("-" * 72)
        for i, u in enumerate(active_users, 1):
            sla = " [SLA]" if getattr(u, "is_sla_manager", False) else ""
            print(f"  {i:<4} {u.email:<48} {u.role:<10} {u.area}{sla}")
        print("-" * 72)
        print(f"  TOTAL: {len(active_users)} active user(s) confirmed in database.")
        print("=" * 60)

    except Exception as e:
        db.rollback()
        print(f"ERROR: Seeding failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    seed_users()
