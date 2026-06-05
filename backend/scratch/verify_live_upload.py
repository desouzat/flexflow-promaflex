import subprocess
import time
import requests
import sys
import os
from pathlib import Path

def run_live_verification():
    print("=== STARTING LIVE UVICORN CSP/UPLOAD LOGS VERIFICATION ===")
    
    scratch_dir = Path(__file__).parent
    log_file_path = scratch_dir / "uvicorn_temp.log"
    if log_file_path.exists():
        try:
            log_file_path.unlink()
        except Exception:
            pass
        
    log_file = open(log_file_path, "w", encoding="utf-8")
    
    # 1. Start Uvicorn backend process on port 8001 to avoid conflicts
    cmd = [
        "backend/venv/Scripts/python", "-m", "uvicorn", 
        "backend.main:app", 
        "--host", "127.0.0.1", 
        "--port", "8001",
        "--log-level", "info"
    ]
    
    print(f"Starting server with command: {' '.join(cmd)}")
    
    server_process = subprocess.Popen(
        cmd,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="ignore",
        env={**os.environ, "TESTING": "true"}
    )
    
    # Wait for server to start
    print("Waiting for server to spin up on http://127.0.0.1:8001...")
    time.sleep(5)
    
    try:
        # Check if process died immediately
        ret = server_process.poll()
        if ret is not None:
            print(f"[FAIL] Server failed to start. Return code: {ret}")
            return False

        # 2. Perform Login to obtain JWT token
        login_url = "http://127.0.0.1:8001/api/auth/login"
        print(f"Logging in to: {login_url}")
        login_resp = requests.post(
            login_url,
            json={"email": "test@example.com", "password": "password123"},
            timeout=10
        )
        
        if login_resp.status_code != 200:
            print(f"[FAIL] Login failed with status {login_resp.status_code}: {login_resp.text}")
            return False
            
        token = login_resp.json().get("access_token")
        if not token:
            print("[FAIL] Access token not found in login response.")
            return False
        print("[OK] Successfully logged in and retrieved JWT token.")
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        # 3. Get POs list to select one for upload
        pos_url = "http://127.0.0.1:8001/api/kanban/pos"
        print(f"Fetching POs from: {pos_url}")
        pos_resp = requests.get(pos_url, headers=headers, timeout=10)
        
        if pos_resp.status_code != 200:
            print(f"[FAIL] Failed to fetch POs: {pos_resp.status_code} {pos_resp.text}")
            return False
            
        pos = pos_resp.json()
        if not pos:
            print("[FAIL] No POs found in database to perform upload verification.")
            return False
            
        target_po = pos[0]
        po_id = target_po["id"]
        print(f"[OK] Selected target PO ID: {po_id}")
        
        # 4. Upload Cargo Photo
        upload_url = f"http://127.0.0.1:8001/api/kanban/pos/{po_id}/upload-cargo-photo"
        print(f"Attempting upload to: {upload_url}")
        
        dummy_file_content = b"fake image bytes representing cargo photo evidence"
        files = {
            "file": ("verification_test.png", dummy_file_content, "image/png")
        }
        
        upload_resp = requests.post(upload_url, headers=headers, files=files, timeout=10)
        
        if upload_resp.status_code != 200:
            print(f"[FAIL] Upload failed with status {upload_resp.status_code}: {upload_resp.text}")
            return False
            
        upload_json = upload_resp.json()
        print("[OK] Upload request succeeded (Status 200).")
        
        # Verify photo path in metadata
        logistics = upload_json.get("partition_metadata", {}).get("logistics_checklist", {})
        photo_path = logistics.get("foto_carga_path")
        if photo_path:
            print(f"[OK] Photo path correctly updated in nested checklist: {photo_path}")
        else:
            print("[FAIL] Photo path NOT found in nested logistics checklist.")
            return False
            
    finally:
        # Terminate server
        print("Stopping Uvicorn server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
            
        log_file.close()
        
        # 5. Read captured stdout logs from server file
        try:
            with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
                stdout_logs = f.read()
        except Exception as read_err:
            stdout_logs = f"[ERROR READING LOG FILE]: {read_err}"
            
        print("\n=== CAPTURED UVICORN LOG STREAM ===")
        print(stdout_logs)
        print("===================================\n")
        
        # Clean up log file
        try:
            log_file_path.unlink()
        except Exception:
            pass
        
        # 6. Check for requested patterns
        has_post_request = "[REQUEST] POST /api/kanban/pos/" in stdout_logs
        has_debug_saving = "DEBUG: Saving file to" in stdout_logs
        has_post_response = "[RESPONSE] POST /api/kanban/pos/" in stdout_logs
        
        if has_post_request and has_debug_saving and has_post_response:
            print("[SUCCESS] All logs verified successfully in Uvicorn output stream.")
            return True
        else:
            print("[FAIL] Verification logs missing from Uvicorn stream.")
            print(f"  - Has request log: {has_post_request}")
            print(f"  - Has debug saving log: {has_debug_saving}")
            print(f"  - Has response log: {has_post_response}")
            return False

if __name__ == "__main__":
    success = run_live_verification()
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
