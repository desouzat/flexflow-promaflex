"""
download_all_s3_files.py
========================
Downloads every .xlsx / .xls file from the S3 'flexflow' bucket
to the local directory:  backend/uploads/

Credentials are loaded from backend/.env.
Run from the project root:
    python backend/scripts/download_all_s3_files.py
"""
import os
import sys

# ── stdout encoding fix for Windows console ────────────────────────────────────
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ── Locate project root and .env ───────────────────────────────────────────────
SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))        # .../backend/scripts
BACKEND_DIR  = os.path.dirname(SCRIPT_DIR)                        # .../backend
PROJECT_ROOT = os.path.dirname(BACKEND_DIR)                       # .../FlexFlow
ENV_PATH     = os.path.join(BACKEND_DIR, '.env')
DEST_DIR     = os.path.join(BACKEND_DIR, 'uploads')

# ── Parse .env manually (no dotenv dependency required) ───────────────────────
env_vars: dict = {}
with open(ENV_PATH, encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        env_vars[key.strip()] = val.strip()

S3_ENDPOINT   = env_vars.get('S3_ENDPOINT', '')
S3_ACCESS_KEY = env_vars.get('S3_ACCESS_KEY', '')
S3_SECRET_KEY = env_vars.get('S3_SECRET_KEY', '')
S3_BUCKET     = env_vars.get('S3_BUCKET_NAME', 'flexflow')

print("=" * 60)
print("S3 BATCH DOWNLOAD — FlexFlow bucket")
print("=" * 60)
print(f"Endpoint : {S3_ENDPOINT}")
print(f"Bucket   : {S3_BUCKET}")
print(f"Dest dir : {DEST_DIR}")
print()

# ── Create destination directory ───────────────────────────────────────────────
os.makedirs(DEST_DIR, exist_ok=True)

# ── Initialise boto3 client ────────────────────────────────────────────────────
try:
    import boto3
    from botocore.exceptions import ClientError, BotoCoreError
except ImportError:
    print("ERROR: boto3 is not installed. Run:  pip install boto3")
    sys.exit(1)

s3 = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
)

# ── List all objects in the bucket ────────────────────────────────────────────
paginator = s3.get_paginator('list_objects_v2')
all_objects = []
for page in paginator.paginate(Bucket=S3_BUCKET):
    for obj in page.get('Contents', []):
        all_objects.append(obj)

print(f"Total objects in bucket : {len(all_objects)}")

xlsx_objects = [
    obj for obj in all_objects
    if obj['Key'].lower().endswith(('.xlsx', '.xls'))
]
print(f"Excel files found       : {len(xlsx_objects)}")
print()

if not xlsx_objects:
    print("No Excel files found in bucket. Nothing to download.")
    sys.exit(0)

# ── Download each Excel file ──────────────────────────────────────────────────
downloaded = []
failed     = []

for obj in sorted(xlsx_objects, key=lambda o: o['LastModified'], reverse=True):
    key       = obj['Key']
    size_kb   = obj['Size'] / 1024
    modified  = obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S UTC')

    # Preserve only the filename, not any S3 key prefix folders
    filename  = os.path.basename(key) or key.replace('/', '_')
    dest_path = os.path.join(DEST_DIR, filename)

    # Skip if already downloaded and same size
    if os.path.exists(dest_path) and os.path.getsize(dest_path) == obj['Size']:
        print(f"  [SKIP]     {filename}  ({size_kb:.1f} KB)  — already present, same size")
        downloaded.append({'key': key, 'filename': filename, 'size_kb': size_kb,
                           'modified': modified, 'status': 'SKIPPED (already present)'})
        continue

    try:
        s3.download_file(S3_BUCKET, key, dest_path)
        actual_kb = os.path.getsize(dest_path) / 1024
        print(f"  [OK]       {filename}  ({actual_kb:.1f} KB)  modified={modified}")
        downloaded.append({'key': key, 'filename': filename, 'size_kb': actual_kb,
                           'modified': modified, 'status': 'DOWNLOADED'})
    except (ClientError, BotoCoreError, Exception) as exc:
        print(f"  [ERROR]    {key}  — {exc}")
        failed.append({'key': key, 'error': str(exc)})

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 60)
print("DOWNLOAD SUMMARY")
print("=" * 60)
print(f"Total Excel files in bucket : {len(xlsx_objects)}")
print(f"Successfully downloaded     : {sum(1 for d in downloaded if d['status'] == 'DOWNLOADED')}")
print(f"Already present (skipped)   : {sum(1 for d in downloaded if 'SKIPPED' in d['status'])}")
print(f"Failed                      : {len(failed)}")
print()
print(f"Local directory: {DEST_DIR}")
print()

if downloaded:
    print("Files in uploads/ after run:")
    for d in downloaded:
        print(f"  {d['status']:<28} {d['filename']}  ({d['size_kb']:.1f} KB)  [{d['modified']}]")

if failed:
    print()
    print("FAILURES:")
    for f in failed:
        print(f"  {f['key']} -> {f['error']}")
    sys.exit(1)

print()
print("Done.")
