import os
import sys
import time
import subprocess
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.orm import Session

# Fix Windows console encoding issues
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

workspace_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(workspace_root))

proxy_binary = workspace_root / "backend" / "cloud-sql-proxy.exe"

proxy_proc = None
if proxy_binary.exists():
    try:
        token_out = subprocess.check_output(['gcloud.cmd', 'auth', 'print-access-token'], stderr=subprocess.STDOUT)
        token = token_out.decode().strip()

        proxy_proc = subprocess.Popen([
            str(proxy_binary),
            'flexflow-promaflex:southamerica-east1:flexflow-db-v1',
            '--port', '5434',
            '--token', token
        ])
        time.sleep(3.5)
    except Exception as e:
        print(f"[WARNING] Could not auto-launch proxy: {e}")

from backend.database import SessionLocal

db: Session = SessionLocal()
try:
    print("=" * 90)
    print("🔍 DIAGNOSTIC AUDIT: COMMERCIAL USER PROFILES")
    print("=" * 90)

    target_emails = [
        'alexandre@promaflex.com.br',
        'douglas_promaflex@grupovelletri.com.br',
        'alessandro.comercial74@gmail.com'
    ]

    # Query target users
    query = text("""
        SELECT id, email, name, role, area, tenant_id, is_active
        FROM users 
        WHERE LOWER(email) IN (:e1, :e2, :e3) OR email LIKE '%alexandre%' OR email LIKE '%douglas%' OR email LIKE '%alessandro%';
    """)
    rows = db.execute(query, {
        "e1": target_emails[0].lower(),
        "e2": target_emails[1].lower(),
        "e3": target_emails[2].lower()
    }).fetchall()

    print(f"\nTarget Users Query Results ({len(rows)} users found):")
    print(f"{'ID':<38} | {'Email':<40} | {'Name':<25} | {'Role':<15} | {'Area':<15} | {'Active':<7}")
    print("-" * 150)
    for r in rows:
        u_id, email, name, role, area, tenant_id, active = r
        print(f"{str(u_id):<38} | {str(email):<40} | {str(name):<25} | {str(role):<15} | {str(area):<15} | {str(active):<7}")

    # Query ALL users to see general roles and areas across the system
    print("\n" + "=" * 90)
    print("ALL USERS IN DATABASE AUDIT")
    print("=" * 90)
    all_users_q = text("SELECT id, email, name, role, area FROM users ORDER BY email;")
    all_rows = db.execute(all_users_q).fetchall()
    for r in all_rows:
        u_id, email, name, role, area = r
        print(f"User: {str(email):<40} | Name: {str(name):<25} | Role: {str(role):<15} | Area: {str(area):<15}")

    print("=" * 90)

except Exception as e:
    print(f"❌ Error during DB audit: {e}")
finally:
    db.close()
    if proxy_proc:
        proxy_proc.terminate()
