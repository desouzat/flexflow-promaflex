import sys
import os

# Add project root directory to path to import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load env variables
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from backend.database import SessionLocal, engine
from backend.models import Tenant, User
from backend.routers.auth import get_password_hash

def run_seeder():
    print("=" * 60)
    print("SEEDING PRIMARY ADMIN ACCOUNT")
    print("=" * 60)
    
    db_url = os.getenv("DATABASE_URL")
    print(f"Configured database URL: {db_url}")
    
    # Try to connect. If fails, try switching port to 5433
    urls_to_try = [db_url]
    if "5434" in db_url:
        urls_to_try.append(db_url.replace("5434", "5433"))
    elif "5433" in db_url:
        urls_to_try.append(db_url.replace("5433", "5434"))
        
    db = None
    connected = False
    for url in urls_to_try:
        try:
            print(f"Connecting to: {url.split('@')[-1]} ...")
            test_engine = create_engine(url)
            LocalSession = sessionmaker(bind=test_engine)
            db = LocalSession()
            # Try a simple query to verify connection
            db.execute(text("SELECT 1"))
            print("Connected successfully!")
            connected = True
            break
        except Exception as e:
            print(f"Connection failed: {e}")
            if db:
                db.close()
                
    if not connected:
        print("[FATAL] Could not connect to database on any attempted port.")
        sys.exit(1)
        
    try:
        # Emergency Database Truncate
        print("Executing Emergency Database Truncate (purchase_orders, order_items, audit_logs)...")
        db.execute(text("TRUNCATE purchase_orders, order_items, audit_logs CASCADE;"))
        db.commit()
        
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
            print(f"Using existing tenant: '{tenant.name}' (ID: {tenant.id})")
            
        # 2. Hash password
        email = "admin@botcase.com.br"
        password = "Proma@2026"
        role = "admin"
        area = "Management"
        name = "System Admin"
        
        print(f"Hashing password for {email}...")
        hashed_pwd = get_password_hash(password)
        
        # 3. Check if user exists
        user = db.query(User).filter(User.email == email).first()
        if user:
            print(f"User {email} already exists. Updating credentials...")
            user.name = name
            user.role = role
            user.area = area
            user.hashed_password = hashed_pwd
            user.is_active = True
            db.add(user)
            print("ADMIN USER UPDATED SUCCESSFULLY")
        else:
            print(f"Creating new admin user {email}...")
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
            print("ADMIN USER CREATED SUCCESSFULLY")
            
        db.commit()
        print("Transaction committed successfully.")
        print("=" * 60)
        sys.exit(0)
        
    except Exception as e:
        db.rollback()
        print(f"[ERROR] Seeding admin user failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_seeder()
