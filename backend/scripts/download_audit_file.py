import os
import sys
import io
from pathlib import Path

if sys.platform == 'win32':
    import io as _io
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Ensure backend and root are in sys.path
workspace_root = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(workspace_root))

from dotenv import load_dotenv
env_path = workspace_root / "backend" / ".env"
load_dotenv(dotenv_path=env_path)

from backend.database import SessionLocal
from backend.services.s3_service import S3Service

def main():
    print("=" * 80)
    print("🚀 TASK 1: IMMEDIATE S3 FILE RECOVERY (07/08)")
    print("=" * 80)

    db = SessionLocal()
    try:
        s3 = S3Service(db)
        if not s3.is_configured():
            print("❌ S3 service is not configured in .env!")
            return

        print("🔍 Searching S3/GCS bucket for Exportacao_20260807_200044.xlsx...")
        
        target_term = "Exportacao_20260807_200044.xlsx"
        matched_key = None

        # 1. Search root and processed files using s3.list_new_files(include_processed=True)
        # Or search s3_client directly to find any match
        response_all = s3.s3_client.list_objects_v2(
            Bucket=s3.bucket_name
        )

        if 'Contents' in response_all:
            for obj in response_all['Contents']:
                key = obj['Key']
                if target_term in key:
                    matched_key = key
                    print(f"✅ Found matching object: Key='{key}', Size={obj['Size']} bytes, Modified={obj['LastModified']}")
                    break

        if not matched_key:
            print(f"⚠️ Target term '{target_term}' not found in direct list. Searching for any file containing '20260807'...")
            if 'Contents' in response_all:
                for obj in response_all['Contents']:
                    if "20260807" in obj['Key']:
                        matched_key = obj['Key']
                        print(f"✅ Found candidate object: Key='{key}', Size={obj['Size']} bytes, Modified={obj['LastModified']}")
                        break

        if not matched_key:
            print("❌ Could not locate 07/08 file in bucket!")
            return

        print(f"⬇️ Downloading file content for key: {matched_key}...")
        content_bytes, filename = s3.download_file(matched_key)

        scratch_dir = workspace_root / "backend" / "scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)

        save_path = scratch_dir / filename
        with open(save_path, "wb") as f:
            f.write(content_bytes)

        file_size = len(content_bytes)
        print(f"\n🎉 SUCCESS: File recovered and saved locally!")
        print(f"📁 Local File Path : {save_path}")
        print(f"📄 Exact File Name : {filename}")
        print(f"📊 File Size       : {file_size:,} bytes ({file_size / 1024:.2f} KB)")
        print("=" * 80)

    except Exception as e:
        print(f"❌ Error during file recovery: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
