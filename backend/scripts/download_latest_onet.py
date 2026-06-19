"""
download_latest_onet.py
-----------------------
Downloads the most recently uploaded file from the S3 bucket 'flexflow'
using credentials stored in backend/.env.

Usage:
    python backend/scripts/download_latest_onet.py
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Resolve paths and load environment variables from backend/.env
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent          # backend/scripts/
BACKEND_DIR = SCRIPT_DIR.parent                       # backend/
PROJECT_DIR = BACKEND_DIR.parent                      # project root
ENV_FILE    = BACKEND_DIR / ".env"

if not ENV_FILE.exists():
    print(f"[ERROR] .env file not found at: {ENV_FILE}")
    sys.exit(1)

# Manual dotenv loader (avoids requiring python-dotenv)
print(f"[INFO] Loading environment variables from: {ENV_FILE}")
with open(ENV_FILE, encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())

# ---------------------------------------------------------------------------
# 2. Read S3 configuration
# ---------------------------------------------------------------------------
S3_ENDPOINT   = os.environ.get("S3_ENDPOINT")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY")
S3_BUCKET     = os.environ.get("S3_BUCKET_NAME", "flexflow")

if not all([S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY]):
    print("[ERROR] Missing one or more S3 environment variables "
          "(S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY).")
    sys.exit(1)

print(f"[INFO] S3 Endpoint : {S3_ENDPOINT}")
print(f"[INFO] S3 Bucket   : {S3_BUCKET}")

# ---------------------------------------------------------------------------
# 3. Initialize boto3 S3 client
# ---------------------------------------------------------------------------
try:
    import boto3
    from botocore.config import Config
except ImportError:
    print("[ERROR] boto3 is not installed. Run: pip install boto3")
    sys.exit(1)

s3_client = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    config=Config(signature_version="s3v4"),
)

# ---------------------------------------------------------------------------
# 4. List all objects and sort by LastModified (descending)
# ---------------------------------------------------------------------------
print(f"\n[INFO] Listing objects in bucket '{S3_BUCKET}' ...")

all_objects = []
paginator = s3_client.get_paginator("list_objects_v2")

try:
    pages = paginator.paginate(Bucket=S3_BUCKET)
    for page in pages:
        contents = page.get("Contents", [])
        all_objects.extend(contents)
except Exception as exc:
    print(f"[ERROR] Failed to list objects: {exc}")
    sys.exit(1)

if not all_objects:
    print(f"[WARNING] Bucket '{S3_BUCKET}' is empty — nothing to download.")
    sys.exit(0)

print(f"[INFO] Found {len(all_objects)} object(s) in the bucket.")

# Sort descending by LastModified
all_objects.sort(key=lambda obj: obj["LastModified"], reverse=True)

# Show the 5 most recent for context
print("\n[INFO] 5 most recently modified objects:")
for i, obj in enumerate(all_objects[:5], 1):
    print(f"  {i}. {obj['Key']:60s}  {obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S %Z')}")

latest = all_objects[0]
latest_key  = latest["Key"]
latest_date = latest["LastModified"].strftime("%Y-%m-%d %H:%M:%S %Z")
print(f"\n[INFO] Latest file: '{latest_key}'  (uploaded {latest_date})")

# ---------------------------------------------------------------------------
# 5. Prepare local destination and download the file
# ---------------------------------------------------------------------------
UPLOAD_DIR = BACKEND_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Keep only the filename part (strip any S3 "folder" prefixes)
filename   = Path(latest_key).name
local_path = UPLOAD_DIR / filename

print(f"[INFO] Downloading to: {local_path}")

try:
    s3_client.download_file(
        Bucket=S3_BUCKET,
        Key=latest_key,
        Filename=str(local_path),
    )
except Exception as exc:
    print(f"[ERROR] Download failed: {exc}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 6. Success report
# ---------------------------------------------------------------------------
size_kb = local_path.stat().st_size / 1024
print(f"\n[SUCCESS] File downloaded successfully!")
print(f"          Name  : {filename}")
print(f"          Path  : {local_path}")
print(f"          Size  : {size_kb:.1f} KB")
print(f"          Dated : {latest_date}")
