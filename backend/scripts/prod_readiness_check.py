import os
import sys
import io
from pathlib import Path
from sqlalchemy import text
import boto3

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add parent directory of backend (workspace root) to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from backend.database import engine

def main():
    print("=" * 60)
    print("🚀 RUNNING PRODUCTION READINESS HARNESS CHECK")
    print("=" * 60)
    
    success = True
    
    # 1. Connection to Google Cloud SQL
    print("\n[CHECK 1/4] Testing Google Cloud SQL Connection...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1")).scalar()
            if result == 1:
                print("✅ Google Cloud SQL connection verified successfully.")
            else:
                print("❌ Google Cloud SQL connection returned unexpected result.")
                success = False
    except Exception as e:
        print(f"❌ Google Cloud SQL connection failed: {e}")
        success = False
        
    # 2. Presence of SECURITY_PEPPER in environment
    print("\n[CHECK 2/4] Testing SECURITY_PEPPER Presence...")
    pepper = os.getenv("SECURITY_PEPPER", "")
    if pepper:
        print(f"✅ SECURITY_PEPPER is present in the environment (length: {len(pepper)}).")
    else:
        print("❌ SECURITY_PEPPER is NOT present in the environment.")
        success = False
        
    # 3. S3 Bucket Connectivity for ONET files
    print("\n[CHECK 3/4] Testing AWS S3 Bucket Connectivity...")
    s3_endpoint = os.getenv("S3_ENDPOINT")
    s3_access_key = os.getenv("S3_ACCESS_KEY")
    s3_secret_key = os.getenv("S3_SECRET_KEY")
    s3_bucket_name = os.getenv("S3_BUCKET_NAME")
    
    if not all([s3_access_key, s3_secret_key, s3_bucket_name]):
        print("❌ S3 Bucket configuration is missing in .env.")
        success = False
    else:
        try:
            s3_client = boto3.client(
                's3',
                endpoint_url=s3_endpoint,
                aws_access_key_id=s3_access_key,
                aws_secret_access_key=s3_secret_key,
                region_name='us-east-1'
            )
            # Check bucket listing
            response = s3_client.list_objects_v2(Bucket=s3_bucket_name, MaxKeys=1)
            print(f"✅ S3 Bucket connectivity verified successfully for bucket '{s3_bucket_name}'.")
        except Exception as e:
            print(f"❌ S3 Bucket connectivity failed: {e}")
            success = False
            
    # 4. Writable check for /backend/uploads directory
    print("\n[CHECK 4/4] Testing /backend/uploads Directory Write Permissions...")
    project_root = Path(__file__).resolve().parent.parent.parent
    uploads_dir = project_root / "backend" / "uploads"
    
    try:
        uploads_dir.mkdir(parents=True, exist_ok=True)
        # Test write by creating a temporary file
        temp_file = uploads_dir / ".write_test"
        temp_file.write_text("write_test_ok")
        # Read to verify
        read_back = temp_file.read_text()
        if read_back == "write_test_ok":
            print(f"✅ /backend/uploads directory is writable by the application ({uploads_dir.resolve()}).")
            temp_file.unlink() # Cleanup
        else:
            print("❌ Write test failed (read value mismatch).")
            success = False
    except Exception as e:
        print(f"❌ Write test failed for directory '{uploads_dir}': {e}")
        success = False

    print("\n" + "=" * 60)
    if success:
        print("🎉 ALL PRODUCTION READINESS CHECKS PASSED SUCCESSFULLY!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("❌ SOME PRODUCTION READINESS CHECKS FAILED. PLEASE VERIFY CONFIGS.")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()
