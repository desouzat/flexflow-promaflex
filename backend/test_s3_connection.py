"""
S3 Connection Test Script
Tests the connection to the Flexflow bucket and lists objects
"""
import sys
import io
import boto3
from botocore.exceptions import ClientError
import os
from dotenv import load_dotenv

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Load environment variables
load_dotenv()

S3_ENDPOINT = os.getenv('S3_ENDPOINT')
S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY')
S3_SECRET_KEY = os.getenv('S3_SECRET_KEY')
S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')

def test_s3_connection():
    """Test S3 connection and list objects"""
    print("=" * 60)
    print("S3 CONNECTION TEST")
    print("=" * 60)
    print(f"Endpoint: {S3_ENDPOINT}")
    print(f"Bucket: {S3_BUCKET_NAME}")
    print(f"Access Key: {S3_ACCESS_KEY[:10]}...")
    print()
    
    try:
        # Create S3 client
        s3_client = boto3.client(
            's3',
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            region_name='us-east-1'
        )
        
        print("✅ S3 Client created successfully")
        print()
        
        # Test bucket access
        print(f"Testing access to bucket '{S3_BUCKET_NAME}'...")
        response = s3_client.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            MaxKeys=10
        )
        
        object_count = response.get('KeyCount', 0)
        print(f"✅ Successfully connected to bucket '{S3_BUCKET_NAME}'!")
        print(f"   Objects found: {object_count}")
        print()
        
        if object_count > 0:
            print("Sample objects in bucket:")
            for obj in response.get('Contents', [])[:10]:
                size_kb = obj['Size'] / 1024
                modified = obj['LastModified'].strftime('%Y-%m-%d %H:%M:%S')
                print(f"  📄 {obj['Key']}")
                print(f"     Size: {size_kb:.2f} KB | Modified: {modified}")
            print()
        else:
            print("⚠️  Bucket is empty. No files found.")
            print()
        
        # Test write permission (optional)
        print("Testing write permissions...")
        test_key = "test_connection.txt"
        test_content = b"FlexFlow S3 Connection Test"
        
        try:
            s3_client.put_object(
                Bucket=S3_BUCKET_NAME,
                Key=test_key,
                Body=test_content
            )
            print(f"✅ Write test successful! Created '{test_key}'")
            
            # Clean up test file
            s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=test_key)
            print(f"✅ Cleanup successful! Deleted '{test_key}'")
        except ClientError as e:
            print(f"⚠️  Write test failed: {e.response.get('Error', {}).get('Message', str(e))}")
        
        print()
        print("=" * 60)
        print("✅ S3 CONNECTION TEST PASSED")
        print("=" * 60)
        print("The background worker can now:")
        print("  • List objects in the bucket")
        print("  • Download Excel files")
        print("  • Process ONET imports automatically")
        print("=" * 60)
        
        return True
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        print(f"❌ AWS Error: {error_code}")
        print(f"   Message: {error_message}")
        print()
        
        if error_code == 'NoSuchBucket':
            print("❌ BUCKET NOT FOUND")
            print(f"   The bucket '{S3_BUCKET_NAME}' does not exist")
            print("   Please verify the bucket name with Márcio")
        elif error_code == 'AccessDenied':
            print("❌ ACCESS DENIED")
            print("   The credentials don't have permission to access this bucket")
        elif error_code == 'InvalidAccessKeyId':
            print("❌ Invalid Access Key")
        elif error_code == 'SignatureDoesNotMatch':
            print("❌ Invalid Secret Key")
        
        return False
        
    except Exception as e:
        print(f"❌ Unexpected error: {type(e).__name__}")
        print(f"   {str(e)}")
        return False

if __name__ == "__main__":
    success = test_s3_connection()
    sys.exit(0 if success else 1)
