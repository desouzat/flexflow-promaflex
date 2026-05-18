"""
S3 Bucket Discovery Script
Attempts to list all buckets in the S3 account to find the correct bucket name
"""
import sys
import io
import boto3
from botocore.exceptions import ClientError

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Real credentials from IT
S3_ENDPOINT = "https://s3-dc3-002.mspclouds.com"
S3_ACCESS_KEY = "ZE7VWSHR2C2E6UGIKKD3"
S3_SECRET_KEY = "p9KflD76SkGTOZlrefGZFZXfi4UXAC1LfdJbJZmB"

def discover_buckets():
    """Discover available S3 buckets"""
    print("=" * 60)
    print("S3 BUCKET DISCOVERY")
    print("=" * 60)
    print(f"Endpoint: {S3_ENDPOINT}")
    print(f"Access Key: {S3_ACCESS_KEY[:10]}...")
    print()
    
    try:
        # Create S3 client
        s3_client = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            region_name='us-east-1'  # Default region
        )
        
        print("✅ S3 Client created successfully")
        print()
        
        # Try to list buckets
        print("Attempting to list all buckets...")
        response = s3_client.list_buckets()
        
        buckets = response.get('Buckets', [])
        
        if not buckets:
            print("⚠️  No buckets found in this account")
            return None
        
        print(f"✅ Found {len(buckets)} bucket(s):")
        print()
        
        target_bucket = None
        for bucket in buckets:
            bucket_name = bucket['Name']
            creation_date = bucket['CreationDate']
            print(f"  📦 {bucket_name}")
            print(f"     Created: {creation_date}")
            
            # Check if bucket name contains flexflow or promaflex
            if 'flexflow' in bucket_name.lower() or 'promaflex' in bucket_name.lower():
                print(f"     ⭐ MATCH! This looks like the target bucket")
                target_bucket = bucket_name
            print()
        
        if target_bucket:
            print("=" * 60)
            print(f"✅ RECOMMENDED BUCKET: {target_bucket}")
            print("=" * 60)
            
            # Try to list objects in the bucket
            print()
            print(f"Testing access to bucket '{target_bucket}'...")
            try:
                objects_response = s3_client.list_objects_v2(
                    Bucket=target_bucket,
                    MaxKeys=5
                )
                
                object_count = objects_response.get('KeyCount', 0)
                print(f"✅ Successfully accessed bucket!")
                print(f"   Objects found: {object_count}")
                
                if object_count > 0:
                    print("   Sample objects:")
                    for obj in objects_response.get('Contents', [])[:5]:
                        print(f"     - {obj['Key']} ({obj['Size']} bytes)")
                
            except ClientError as e:
                print(f"⚠️  Could not list objects: {e}")
            
            return target_bucket
        else:
            print("=" * 60)
            print("⚠️  No bucket name contains 'flexflow' or 'promaflex'")
            print("   Please ask Márcio for the exact bucket name")
            print("=" * 60)
            return None
            
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        print(f"❌ AWS Error: {error_code}")
        print(f"   Message: {error_message}")
        print()
        
        if error_code == 'AccessDenied':
            print("⚠️  ACCESS DENIED: Cannot list buckets")
            print("   This means the credentials work, but don't have permission to list buckets")
            print("   You MUST ask Márcio for the exact bucket name")
        elif error_code == 'InvalidAccessKeyId':
            print("❌ Invalid Access Key - check credentials")
        elif error_code == 'SignatureDoesNotMatch':
            print("❌ Invalid Secret Key - check credentials")
        else:
            print("❌ Unexpected error - check endpoint and credentials")
        
        return None
        
    except Exception as e:
        print(f"❌ Unexpected error: {type(e).__name__}")
        print(f"   {str(e)}")
        return None

if __name__ == "__main__":
    bucket_name = discover_buckets()
    
    if bucket_name:
        print()
        print("=" * 60)
        print("NEXT STEPS:")
        print("=" * 60)
        print(f"1. Update backend/.env with:")
        print(f"   S3_BUCKET_NAME={bucket_name}")
        print(f"2. Test the S3 integration")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("NEXT STEPS:")
        print("=" * 60)
        print("1. Ask Márcio for the exact S3 bucket name")
        print("2. Update backend/.env with the bucket name")
        print("=" * 60)
