import os
import sys
from pathlib import Path

# Add root directory to path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir.parent))

from dotenv import load_dotenv
load_dotenv(backend_dir / ".env")

from passlib.context import CryptContext
from backend.routers.auth import get_password_hash, verify_password, SECURITY_PEPPER

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def run_pepper_verification():
    print("=" * 60)
    print("SECURITY PEPPER VERIFICATION HARNESS (H-01)")
    print("=" * 60)
    
    password = "Proma@2026_test_password"
    print(f"Original Password: {password}")
    print(f"Loaded SECURITY_PEPPER length: {len(SECURITY_PEPPER)} characters")
    
    # Hash password using our helper
    hashed = get_password_hash(password)
    print(f"Hashed Password: {hashed}")
    
    # Test 1: Verify using our verify_password (should succeed)
    success_with_helper = verify_password(password, hashed)
    print(f"Verification using verify_password helper: {success_with_helper} (expected: True)")
    
    # Test 2: Verify without pepper using raw pwd_context (should fail)
    try:
        success_without_pepper = pwd_context.verify(password, hashed)
    except Exception as e:
        success_without_pepper = False
        print(f"Error during raw verification: {e}")
    print(f"Verification WITHOUT pepper (raw pwd_context): {success_without_pepper} (expected: False)")
    
    # Test 3: Verify with pepper using raw pwd_context (should succeed)
    peppered_password = password + SECURITY_PEPPER
    success_with_pepper = pwd_context.verify(peppered_password, hashed)
    print(f"Verification WITH pepper (raw pwd_context): {success_with_pepper} (expected: True)")
    
    # Verification check
    if success_with_helper and not success_without_pepper and success_with_pepper:
        print("PEPPER LAYER STATUS: SECURED AND VERIFIED!")
        return 0
    else:
        print("PEPPER LAYER STATUS: VERIFICATION FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(run_pepper_verification())
