"""
Task 1: Download ONET S3 files for 16/07/2026 and 17/07/2026.
Saves to backend/scratch/ folder.
Read-only from S3 — no writes to database.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import boto3

# Windows encoding fix
if sys.platform == 'win32':
    import io as _io
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load .env from backend/
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

S3_ENDPOINT   = os.getenv("S3_ENDPOINT")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_BUCKET     = os.getenv("S3_BUCKET_NAME", "flexflow")

# Target directory
DEST_DIR = Path(__file__).resolve().parent.parent / "scratch"
DEST_DIR.mkdir(parents=True, exist_ok=True)

# Filename patterns to match (search across ALL S3 keys, not just root)
# Jul 16 → Exportacao_20260716_*.xlsx (in raw OR processed/)
# Jul 17 → Exportacao_20260717_*.xlsx (in raw OR processed/)
DATE_PATTERNS = ["20260716", "20260717"]

def matches(key: str) -> bool:
    name = key.split("/")[-1]   # strip folder prefix
    return (
        any(pat in name for pat in DATE_PATTERNS)
        and name.lower().startswith("exportacao")
        and name.lower().endswith(".xlsx")
    )

def main():
    print("=" * 70)
    print("  Task 1: Download ONET S3 files — 16/07 & 17/07/2026")
    print("=" * 70)
    print(f"  Bucket      : {S3_BUCKET}")
    print(f"  Endpoint    : {S3_ENDPOINT}")
    print(f"  Destination : {DEST_DIR}")
    print()

    if not all([S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY]):
        print("❌  Missing S3 credentials in backend/.env")
        sys.exit(1)

    s3 = boto3.client(
        's3',
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS_KEY,
        aws_secret_access_key=S3_SECRET_KEY,
        region_name='us-east-1',
    )

    paginator = s3.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=S3_BUCKET)

    downloaded = []
    skipped    = []

    for page in pages:
        for obj in page.get('Contents', []):
            key  = obj['Key']
            size = obj['Size']
            name = key.split("/")[-1]

            if not matches(key):
                continue

            dest = DEST_DIR / name
            print(f"  ↓ {name}  ({size:,} bytes) ...", end=" ")
            try:
                s3.download_file(S3_BUCKET, key, str(dest))
                actual = dest.stat().st_size
                downloaded.append((name, actual))
                print(f"OK  →  saved {actual:,} bytes")
            except Exception as e:
                skipped.append((name, str(e)))
                print(f"FAILED: {e}")

    print()
    print("=" * 70)
    print(f"  DOWNLOADED : {len(downloaded)} file(s)")
    for name, sz in downloaded:
        print(f"    ✅  {name}   ({sz:,} bytes)")
    if skipped:
        print(f"\n  FAILED : {len(skipped)}")
        for name, err in skipped:
            print(f"    ❌  {name}  — {err}")
    if not downloaded and not skipped:
        print("  ⚠  No files matching Exportacao_20260716_* or Exportacao_20260717_* found in bucket.")
    print("=" * 70)

if __name__ == "__main__":
    main()
