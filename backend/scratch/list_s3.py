import os, sys
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
print(f'Bucket: {bucket}')
paginator = s3.get_paginator('list_objects_v2')
found = []
for page in paginator.paginate(Bucket=bucket):
    for obj in page.get('Contents', []):
        key = obj['Key']
        if '20260716' in key or '20260717' in key or 'Exportacao' in key:
            found.append((key, obj['Size']))
            print(f'  {key}  ({obj["Size"]:,} bytes)')
if not found:
    print('  No matching files found in any folder.')
