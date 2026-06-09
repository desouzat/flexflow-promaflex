import requests

def main():
    base_url = "https://flexflow-app-vbq2onid5a-rj.a.run.app/api"
    po_id = "e040088e-13da-41f8-b11c-acc6b7d0ec0b"
    
    # 1. Login
    login_url = f"{base_url}/auth/login"
    print(f"Logging in to production: {login_url}")
    login_resp = requests.post(
        login_url,
        json={"email": "admin@botcase.com.br", "password": "Proma@2026"},
        timeout=15
    )
    
    if login_resp.status_code != 200:
        print(f"[FAIL] Login failed with status {login_resp.status_code}: {login_resp.text}")
        return
        
    token = login_resp.json().get("access_token")
    if not token:
        print("[FAIL] Access token not found in login response.")
        return
    print("[OK] Successfully logged in to production and retrieved JWT token.")
    
    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    # 2. Upload cargo photo
    upload_url = f"{base_url}/kanban/pos/{po_id}/upload-cargo-photo"
    print(f"Attempting production upload to: {upload_url}")
    
    dummy_file_content = b"fake image bytes representing cargo photo evidence for promaflex"
    files = {
        "file": ("production_debug_cargo.png", dummy_file_content, "image/png")
    }
    
    upload_resp = requests.post(upload_url, headers=headers, files=files, timeout=30)
    
    print(f"Upload Response Status Code: {upload_resp.status_code}")
    print(f"Upload Response Content: {upload_resp.text}")

if __name__ == "__main__":
    main()
