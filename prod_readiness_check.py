"""
FlexFlow — Production Readiness Check Entry Point
==================================================
Root-level convenience wrapper that delegates to the canonical script at
backend/scripts/prod_readiness_check.py

Usage (from project root):
    python prod_readiness_check.py

Environment requirements:
    - Google Cloud SQL Proxy must be running on Port 5434
    - Backend .env must be correctly configured at backend/.env
    - AWS S3 credentials must be present in .env (S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET_NAME)
    - SECURITY_PEPPER must be set in .env
"""

import sys
import runpy
from pathlib import Path

# Resolve the canonical script location
_script_path = Path(__file__).resolve().parent / "backend" / "scripts" / "prod_readiness_check.py"

if not _script_path.exists():
    print(f"❌ ERROR: Canonical script not found at: {_script_path}", file=sys.stderr)
    sys.exit(1)

# Execute the canonical script in-process so sys.path and env are shared
runpy.run_path(str(_script_path), run_name="__main__")
