import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
import boto3

# Fix Windows console encoding issues
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Get the directory where this script is located and resolve backend/.env
current_dir = Path(__file__).resolve().parent
env_path = current_dir.parent / '.env'

# Load .env
load_dotenv(dotenv_path=env_path)

S3_ENDPOINT = os.getenv("S3_ENDPOINT")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "flexflow")

DEST_DIR = r"C:\Documentos\BotCase\FlexFlow\backend\uploads"

def main():
    print("=" * 80)
    print("📥 S3 BATCH DOWNLOAD UTILITY")
    print("=" * 80)
    
    # Ensure destination directory exists
    os.makedirs(DEST_DIR, exist_ok=True)
    print(f"Destination folder: {DEST_DIR}")
    
    if not all([S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY]):
        print("❌ Error: Missing S3 credentials in backend/.env")
        sys.exit(1)
        
    print(f"Connecting to S3 endpoint: {S3_ENDPOINT}")
    print(f"Target Bucket: {S3_BUCKET_NAME}")
    
    try:
        s3_client = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            region_name='us-east-1'
        )

        
        # July 15th, 2026 (inclusive)
        start_date = datetime(2026, 7, 15, 0, 0, 0, tzinfo=timezone.utc)
        end_date = datetime(2026, 7, 15, 23, 59, 59, tzinfo=timezone.utc)
        print(f"Filtering files modified between: {start_date.strftime('%Y-%m-%d %H:%M:%S')} and {end_date.strftime('%Y-%m-%d %H:%M:%S')} UTC")

        
        print("\nListing bucket objects...")
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=S3_BUCKET_NAME)
        
        files_found = 0
        files_downloaded = 0
        
        print(f"\n{'File Key':<50} | {'Last Modified':<25} | {'Status':<15}")
        print("-" * 96)
        
        for page in pages:
            if 'Contents' not in page:
                continue
            for obj in page['Contents']:
                key = obj['Key']
                last_modified = obj['LastModified']
                size = obj['Size']
                
                # Check extension (.xlsx or .xls)
                is_excel = key.lower().endswith(('.xlsx', '.xls'))
                
                # Check modification date
                is_in_range = start_date <= last_modified <= end_date
                
                if is_excel and is_in_range:
                    files_found += 1

                    
                    # Target local path
                    # Extract file name from key (handling possible prefixes/folders in S3)
                    filename = os.path.basename(key)
                    local_path = os.path.join(DEST_DIR, filename)
                    
                    try:
                        # Download file
                        s3_client.download_file(S3_BUCKET_NAME, key, local_path)
                        status = "DOWNLOADED"
                        files_downloaded += 1
                    except Exception as e:
                        status = f"FAILED: {e}"
                        
                    print(f"{key:<50} | {last_modified.strftime('%Y-%m-%d %H:%M:%S'):<25} | {status:<15}")
                    
        print("-" * 96)
        print(f"\nSummary:")
        print(f"  Total matching files found: {files_found}")
        print(f"  Successfully downloaded: {files_downloaded}")
        
    except Exception as e:
        print(f"❌ Error during S3 operation: {e}")
        sys.exit(1)
        
    print("=" * 80)

if __name__ == "__main__":
    main()
