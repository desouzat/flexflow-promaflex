"""Download the Jul 16 and Jul 17 files directly by their known S3 keys."""
import os
from pathlib import Path
from dotenv import load_dotenv
import boto3

load_dotenv(Path('backend/.env'))
s3 = boto3.client('s3',
    endpoint_url=os.getenv('S3_ENDPOINT'),
    aws_access_key_id=os.getenv('S3_ACCESS_KEY'),
    aws_secret_access_key=os.getenv('S3_SECRET_KEY'),
    region_name='us-east-1'
)
bucket = os.getenv('S3_BUCKET_NAME', 'flexflow')
dest = Path('backend/scratch')
dest.mkdir(parents=True, exist_ok=True)

# Known keys from the bucket listing
TARGETS = [
    ("processed/20260717_183110_Exportacao_20260716_200001.xlsx",
     "Exportacao_20260716_200001.xlsx"),
    ("processed/20260721_172102_Exportacao_20260717_200058.xlsx",
     "Exportacao_20260717_200058.xlsx"),
]

print(f"Bucket : {bucket}")
print(f"Dest   : {dest.resolve()}")
print()
for key, local_name in TARGETS:
    local_path = dest / local_name
    print(f"  Downloading {key} ...", end=" ", flush=True)
    try:
        s3.download_file(bucket, key, str(local_path))
        size = local_path.stat().st_size
        print(f"OK — {size:,} bytes  →  {local_name}")
    except Exception as e:
        print(f"FAILED: {e}")
