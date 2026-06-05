import os
from pathlib import Path

def check_uploads_write_permission():
    uploads_dir = Path(__file__).parent.parent / "uploads"
    test_file = uploads_dir / "write_test.txt"
    
    print(f"DEBUG: Target uploads directory: {uploads_dir.resolve()}")
    print(f"DEBUG: Target test file: {test_file.resolve()}")
    
    # Ensure uploads directory exists
    try:
        uploads_dir.mkdir(parents=True, exist_ok=True)
        print("[OK] Uploads directory exists or was created successfully.")
    except Exception as e:
        print(f"[ERROR] Failed to create uploads directory: {e}")
        return False
        
    # Attempt to write dummy content
    try:
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("DUMMY WRITE TEST FOR SOLUTIONS ENGINEER VERIFICATION")
        print("[OK] Successfully wrote dummy file to uploads directory.")
    except Exception as e:
        print(f"[ERROR] Failed to write file to uploads directory: {e}")
        return False
        
    # Attempt to read and clean up
    try:
        with open(test_file, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"[OK] Read back content: '{content}'")
        
        # Remove test file
        test_file.unlink()
        print("[OK] Successfully cleaned up test file.")
        return True
    except Exception as e:
        print(f"[ERROR] Error reading or cleaning up test file: {e}")
        return False

if __name__ == "__main__":
    success = check_uploads_write_permission()
    if success:
        print("\n[SUCCESS] Write permissions to backend/uploads are 100% functional.")
    else:
        print("\n[FAILURE] Write permissions check failed.")
