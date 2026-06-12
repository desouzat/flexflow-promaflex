"""
GCS Write Permission Test — FF-HARDENING-008
Tests whether the active service account credentials in backend/gcp-key.json
have Storage Object Creator / Admin rights on the production bucket.
"""
import os
import sys
import json
import io
import time

# Ensure credentials are loaded from gcp-key.json
key_path = os.path.join(os.path.dirname(__file__), "..", "gcp-key.json")
key_path = os.path.abspath(key_path)
if os.path.exists(key_path):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = key_path
    print(f"[INFO] Loaded credentials from: {key_path}")
    # Print service account email
    with open(key_path) as f:
        key_data = json.load(f)
    print(f"[INFO] Service account: {key_data.get('client_email', 'unknown')}")
    print(f"[INFO] Project ID:      {key_data.get('project_id', 'unknown')}")
else:
    print(f"[WARN] gcp-key.json not found at {key_path}, using ADC/env credentials")

try:
    from google.cloud import storage
except ImportError:
    print("[FATAL] google-cloud-storage not installed.")
    sys.exit(1)

BUCKET_NAME = os.getenv("GCP_BUCKET_NAME", "flexflow-attachments-224292950652")
TEST_BLOB   = f"write-test/{int(time.time())}_ci_write_test.txt"
TEST_CONTENT = b"FlexFlow GCS write permission test - FF-HARDENING-008"

print(f"\n[TEST] Bucket:   {BUCKET_NAME}")
print(f"[TEST] Blob:     {TEST_BLOB}")

# ── Step 1: Initialize client ─────────────────────────────────────────────────
try:
    client = storage.Client()
    print(f"[OK]  Client initialized. Project: {client.project}")
except Exception as e:
    print(f"[FAIL] Could not create storage.Client(): {e}")
    sys.exit(1)

# ── Step 2: Get bucket handle ─────────────────────────────────────────────────
try:
    bucket = client.bucket(BUCKET_NAME)
    print(f"[OK]  Bucket handle acquired: {BUCKET_NAME}")
except Exception as e:
    print(f"[FAIL] Could not get bucket: {e}")
    sys.exit(1)

# ── Step 3: Attempt write ─────────────────────────────────────────────────────
try:
    blob = bucket.blob(TEST_BLOB)
    blob.upload_from_file(io.BytesIO(TEST_CONTENT), content_type="text/plain")
    public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{TEST_BLOB}"
    print(f"\n[SUCCESS] GCS WRITE PERMISSION CONFIRMED")
    print(f"[SUCCESS] Blob created at: {public_url}")
except Exception as e:
    print(f"\n[FAIL] WRITE FAILED: {e}")
    print("\n[DIAGNOSIS] The GCP service account does NOT have Storage Object Creator")
    print("            or Storage Object Admin on this bucket.")
    print("            Fix: In GCP IAM Console, grant the SA 'Storage Object Admin'")
    print("            on bucket flexflow-attachments-224292950652, then redeploy.")
    sys.exit(1)

# ── Step 4: Verify the blob can be read back ──────────────────────────────────
try:
    blob2 = bucket.blob(TEST_BLOB)
    data  = blob2.download_as_bytes()
    assert data == TEST_CONTENT, "Content mismatch!"
    print(f"[OK]  Read-back verified. Content matches.")
except Exception as e:
    print(f"[WARN] Write succeeded but read-back failed: {e}")

# ── Step 5: Cleanup ───────────────────────────────────────────────────────────
try:
    blob.delete()
    print(f"[OK]  Test blob deleted (cleanup).")
except Exception as e:
    print(f"[WARN] Could not delete test blob: {e}")

print("\n[RESULT] GCS bucket is fully writable. Backend upload endpoints should work.")
print("[RESULT] If uploads still fail in the app, the error is elsewhere (URL routing, CORS, etc.)")
