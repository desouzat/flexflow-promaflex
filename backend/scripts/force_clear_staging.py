import os
import sys
import time
import subprocess
from pathlib import Path
from sqlalchemy.orm import Session

# Fix Windows console encoding issues
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory of backend (workspace root) to sys.path
workspace_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(workspace_root))

proxy_binary = workspace_root / "backend" / "cloud-sql-proxy.exe"

# Start Proxy with token if binary exists
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
        time.sleep(3.5) # Wait for proxy socket listener to open
    except Exception as e:
        print(f"[WARNING] Could not auto-launch proxy: {e}")

from backend.database import SessionLocal
from backend.models import StagingSession

db: Session = SessionLocal()
try:
    deleted_rows = db.query(StagingSession).filter(
        StagingSession.tenant_id == '23c431b9-da55-4098-9628-c86df8070b7c' # PromaFlex
    ).delete()
    db.commit()
    print(f"[SUCCESS] Brute-force purge complete. Deleted {deleted_rows} staging session rows.")
except Exception as e:
    db.rollback()
    print(f"[ERROR] Failed to purge: {str(e)}")
finally:
    db.close()
    if proxy_proc:
        proxy_proc.terminate()
