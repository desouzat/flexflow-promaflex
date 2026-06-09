import sys
import os

# Add project root directory to path to import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.orm import Session
from backend.database import SessionLocal
from backend.models import Tenant, User
from backend.routers.auth import get_password_hash

def create_super_admin():
    print("=" * 60)
    print("CREATING SUPER ADMIN USER")
    print("=" * 60)
    
    db: Session = SessionLocal()
    try:
        # 1. Find or create the PromaFlex tenant
        tenant_name = "PromaFlex"
        tenant_cnpj = "12.345.678/0001-90"
        
        tenant = db.query(Tenant).filter(Tenant.name == tenant_name).first()
        if not tenant:
            tenant = db.query(Tenant).filter(Tenant.cnpj == tenant_cnpj).first()
            
        if not tenant:
            print(f"Tenant '{tenant_name}' not found. Creating tenant...")
            tenant = Tenant(
                name=tenant_name,
                cnpj=tenant_cnpj,
                is_active=True
            )
            db.add(tenant)
            db.commit()  # Commit tenant first to avoid ForeignKeyViolation
            db.refresh(tenant)
            print(f"Tenant created and committed with ID: {tenant.id}")
        else:
            print(f"Using existing tenant: '{tenant.name}' (ID: {tenant.id})")
        
        # 2. Define user details
        email = "admin@botcase.com.br"
        password = "Proma@2026"
        role = "admin"
        area = "Management"
        name = "Super Admin"
        
        # 3. Hash password
        print("Generating password hash...")
        hashed_pwd = get_password_hash(password)
        
        # 4. Check if user already exists
        user = db.query(User).filter(User.email == email).first()
        if user:
            print(f"User {email} already exists. Updating existing user...")
            user.tenant_id = tenant.id
            user.name = name
            user.role = role
            user.area = area
            user.hashed_password = hashed_pwd
            user.is_active = True
            db.add(user)
        else:
            print(f"Creating new super admin user: {email}...")
            user = User(
                tenant_id=tenant.id,
                name=name,
                email=email,
                hashed_password=hashed_pwd,
                role=role,
                area=area,
                is_active=True
            )
            db.add(user)
            
        db.commit()
        print("\n" + "=" * 60)
        print("ADMIN CREATED")
        print("=" * 60)
        sys.exit(0)
        
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Failed to create super admin: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    create_super_admin()
