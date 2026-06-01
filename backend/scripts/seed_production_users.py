"""
Production User Seeding Script
Seeds standard production users for FlexFlow departments:
Comercial, Financeiro, Expedição, PCP, Embalagem
"""

import sys
import os
import uuid
from datetime import datetime
from passlib.context import CryptContext

# Insert current working directory to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.database import SessionLocal, engine, Base
from backend.models import Tenant, User

def seed_users():
    print("Starting production user seeding...")
    db = SessionLocal()
    pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
    default_password = "Promaflex@2026"
    hashed_pwd = pwd_context.hash(default_password)
    
    try:
        # 1. Ensure we have at least one tenant (PromaFlex)
        tenant = db.query(Tenant).filter(Tenant.cnpj == "12.345.678/0001-90").first()
        if not tenant:
            tenant = db.query(Tenant).first()
            
        if not tenant:
            print("No tenant found. Creating default 'PromaFlex' tenant...")
            tenant = Tenant(
                id=uuid.uuid4(),
                name="PromaFlex",
                cnpj="12.345.678/0001-90",
                is_active=True
            )
            db.add(tenant)
            db.flush()
            print(f"Created default tenant PromaFlex with ID: {tenant.id}")
        else:
            print(f"Using existing tenant: {tenant.name} ({tenant.cnpj}) with ID: {tenant.id}")
            
        # 2. Define the production users by area
        production_users = {
            "Comercial": ["Mairla", "Jader", "Marcelo", "Andrea", "Barbara"],
            "Financeiro": ["Anderson", "Alex", "Cristiane"],
            "Expedição": ["Fabio", "Gabriel", "Sivonildo"],
            "PCP": ["Jonata", "Cristiano", "Rogerio", "Claudio"],
            "Embalagem": ["Ericleston"]
        }
        
        users_added = 0
        users_updated = 0
        
        for area, names in production_users.items():
            for name in names:
                username = name.lower()
                email = f"{username}@promaflex.com.br"
                
                # Check if user already exists
                existing_user = db.query(User).filter(
                    (User.email == email) | (User.name == name)
                ).first()
                
                if existing_user:
                    print(f"User {name} already exists. Updating area to '{area}'...")
                    existing_user.area = area
                    existing_user.role = "user"  # Ensure correct role
                    existing_user.tenant_id = tenant.id
                    users_updated += 1
                else:
                    print(f"Creating user {name} under department '{area}'...")
                    new_user = User(
                        id=uuid.uuid4(),
                        tenant_id=tenant.id,
                        name=name,
                        email=email,
                        hashed_password=hashed_pwd,
                        role="user",
                        area=area,
                        is_active=True,
                        created_at=datetime.utcnow()
                    )
                    db.add(new_user)
                    users_added += 1
                    
        db.commit()
        print("\nSeeding complete!")
        print(f"Users Added: {users_added}")
        print(f"Users Updated: {users_updated}")
        print(f"All seeded users can log in using the password: '{default_password}'")
        
    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    seed_users()
