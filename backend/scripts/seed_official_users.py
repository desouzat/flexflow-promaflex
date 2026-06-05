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

# List of official users to seed
OFFICIAL_USERS = [
    {"area": "Comercial", "email": "mairla@promaflex.com.br", "role": "operator", "name": "Mairla"},
    {"area": "Comercial", "email": "jader@promaflex.com.br", "role": "operator", "name": "Jader"},
    {"area": "Comercial", "email": "mvelletri_promaflex@grupovelletri.com.br", "role": "operator", "name": "Mvelletri Promaflex"},
    {"area": "Comercial", "email": "barbara@bardge.com.br", "role": "operator", "name": "Barbara"},
    {"area": "Financeiro", "email": "anderson.moreno@promaflex.com.br", "role": "master", "name": "Anderson Moreno"},
    {"area": "Financeiro", "email": "alex@promaflex.com.br", "role": "master", "name": "Alex"},
    {"area": "Financeiro", "email": "cristiane.oliveira@promaflex.com.br", "role": "master", "name": "Cristiane Oliveira"},
    {"area": "Expedição", "email": "fabio_promaflex@grupovelletri.com.br", "role": "operator", "name": "Fabio Promaflex"},
    {"area": "Expedição", "email": "gabriel_promaflex@grupovelletri.com.br", "role": "operator", "name": "Gabriel Promaflex"},
    {"area": "Expedição", "email": "expedicao@promaflex.com.br", "role": "operator", "name": "Expedicao"},
    {"area": "PCP", "email": "jonata_promaflex@grupovelletri.com.br", "role": "operator", "name": "Jonata Promaflex"},
    {"area": "PCP", "email": "cristiano_promaflex@grupovelletri.com.br", "role": "operator", "name": "Cristiano Promaflex"},
    {"area": "PCP", "email": "rogerio_promaflex@grupovelletri.com.br", "role": "operator", "name": "Rogerio Promaflex"},
    {"area": "PCP", "email": "claudio.xavier@grupovelletri.com.br", "role": "operator", "name": "Claudio Xavier"},
    {"area": "Embalagem", "email": "embalagem_promaflex@grupovelletri.com.br", "role": "operator", "name": "Embalagem Promaflex"},
    {"area": "Management", "email": "andrea@grupovelletri.com.br", "role": "master", "name": "Andrea"}
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
        processed_count = 0
        for user_info in OFFICIAL_USERS:
            email = user_info["email"]
            role = user_info["role"]
            area = user_info["area"]
            name = user_info["name"]
            
            # Check if user exists by email
            existing_user = db.query(User).filter(User.email == email).first()
            
            if existing_user:
                print(f"User {email} already exists. Updating area='{area}', role='{role}'...")
                existing_user.name = name
                existing_user.area = area
                existing_user.role = role
                existing_user.hashed_password = hashed_pwd
                existing_user.is_active = True
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
                    is_active=True
                )
                db.add(new_user)
                status_str = "CREATED"
                
            processed_count += 1
            print(f"  [{processed_count:02d}/16] {email} -> {status_str}")
            
        db.commit()
        print("=" * 60)
        print(f"SUCCESS: Seeding completed! {processed_count} users processed.")
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
