"""
test_upload_integration.py
FF-HARDENING-008 — End-to-End Upload Integration Harness
=========================================================
"""

import os
import sys
import json
import time
import io
import requests
from datetime import datetime

# Force UTF-8 on Windows CMD so unicode chars print correctly
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import os
import sys
import json
import time
import tempfile
import io
import requests
from datetime import datetime

# ── Load .env from backend/ ──────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

DATABASE_URL = os.getenv("DATABASE_URL", "")
SECRET_KEY   = os.getenv("SECRET_KEY", "")

# ── Config ───────────────────────────────────────────────────────────────────
API_BASE   = "http://127.0.0.1:8001/api"
LOGIN_URL  = f"{API_BASE}/auth/login"
ADMIN_EMAIL    = "thiago@botcase.net"
ADMIN_PASSWORD = "Proma@2026"

# ANSI colours for terminal output
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def banner(msg): print(f"\n{'='*60}\n{CYAN}{msg}{RESET}\n{'='*60}")
def ok(msg):     print(f"  {GREEN}[OK]   {msg}{RESET}")
def fail(msg):   print(f"  {RED}[FAIL] {msg}{RESET}")
def info(msg):   print(f"  {YELLOW}[INFO] {msg}{RESET}")

# ── DB helper ─────────────────────────────────────────────────────────────────
def get_db_conn():
    import psycopg2
    from urllib.parse import urlparse, unquote
    p = urlparse(DATABASE_URL)
    return psycopg2.connect(
        host=p.hostname,
        port=p.port or 5434,
        dbname=p.path.lstrip('/'),
        user=p.username,
        password=unquote(p.password or ''),
        connect_timeout=10
    )

# ── Create a fake PNG in memory ───────────────────────────────────────────────
def make_fake_image(name: str = "test_cargo_fake.jpg") -> tuple[bytes, str]:
    """Return (bytes, filename). Uses PIL if available, else raw minimal JPEG."""
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (200, 150), color=(255, 140, 0))
        d = ImageDraw.Draw(img)
        d.text((10, 60), "FlexFlow Test", fill=(255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue(), name
    except ImportError:
        # Minimal valid JPEG fallback (1×1 white pixel)
        JPEG_1x1 = (
            b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
            b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
            b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
            b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=8'
            b'\x836...*100\x1c\x1c\x1c\xff\xc0\x00\x0b\x08\x00\x01\x00\x01'
            b'\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01'
            b'\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04'
            b'\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00'
            b'\xfb\xd0\xff\xd9'
        )
        return JPEG_1x1, name

# ─────────────────────────────────────────────────────────────────────────────
def run():
    banner("FF-HARDENING-008 · Upload Integration Harness")
    print(f"  Timestamp : {datetime.now().isoformat()}")
    print(f"  API Base  : {API_BASE}")
    print(f"  DB URL    : {DATABASE_URL[:50]}...")

    results = []

    # ── STEP 1: Verify DB connectivity ────────────────────────────────────────
    banner("STEP 1 · Database Connectivity")
    try:
        conn = get_db_conn()
        cur  = conn.cursor()
        cur.execute("SELECT version();")
        ver = cur.fetchone()[0]
        ok(f"Connected to DB: {ver[:60]}")
        results.append(("DB connectivity", True))
    except Exception as e:
        fail(f"Cannot connect to DB: {e}")
        results.append(("DB connectivity", False))
        print(f"\n{RED}ABORT: Database unreachable — cannot continue.{RESET}")
        _print_summary(results)
        sys.exit(1)

    # ── STEP 2: Find a real PO in the 'Faturamento' stage ────────────────────
    banner("STEP 2 · Locate a Test Purchase Order")
    try:
        cur.execute("""
            SELECT id, status_macro, partition_metadata
            FROM purchase_orders
            WHERE status_macro IN (
                'FATURAMENTO', 'EXPEDICAO', 'SHIPPING', 'Faturamento',
                'Expedição', 'faturamento', 'expedicao'
            )
            LIMIT 5;
        """)
        rows = cur.fetchall()
        if not rows:
            # Fall back to ANY PO
            cur.execute("SELECT id, status_macro, partition_metadata FROM purchase_orders LIMIT 5;")
            rows = cur.fetchall()

        if not rows:
            fail("No purchase_orders found in DB. Cannot run upload test.")
            results.append(("Locate test PO", False))
            _print_summary(results)
            sys.exit(1)

        test_po_id     = rows[0][0]
        test_po_status = rows[0][1]
        info(f"Found {len(rows)} PO(s). Using PO id={test_po_id!r} | status_macro={test_po_status!r}")
        ok(f"Test PO selected: {test_po_id}")
        results.append(("Locate test PO", True))
    except Exception as e:
        fail(f"Query failed: {e}")
        results.append(("Locate test PO", False))
        _print_summary(results)
        sys.exit(1)

    # ── STEP 3: Authenticate → get JWT token ──────────────────────────────────
    banner("STEP 3 · Authenticate (get JWT token)")
    try:
        resp = requests.post(
            LOGIN_URL,
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=45
        )
        resp.raise_for_status()
        token = resp.json().get("access_token") or resp.json().get("token")
        if not token:
            raise ValueError(f"No token in response: {resp.text[:200]}")
        ok(f"JWT obtained (first 20 chars): {token[:20]}...")
        headers = {"Authorization": f"Bearer {token}"}
        results.append(("JWT authentication", True))
    except Exception as e:
        fail(f"Login failed: {e}")
        results.append(("JWT authentication", False))
        info("Cannot test upload without a valid JWT. Is the backend running? (uvicorn backend.main:app --reload)")
        _print_summary(results)
        sys.exit(1)

    # ── STEP 4: Upload cargo photo ─────────────────────────────────────────────
    banner("STEP 4 · Upload Cargo Photo (foto_carga_path)")
    cargo_url = f"{API_BASE}/kanban/pos/{test_po_id}/upload-cargo-photo"
    cargo_bytes, cargo_name = make_fake_image("test_cargo_fake.jpg")
    try:
        info(f"POST → {cargo_url}")
        info(f"File  → {cargo_name} ({len(cargo_bytes)} bytes)")
        t0 = time.time()
        resp = requests.post(
            cargo_url,
            headers=headers,
            files={"file": (cargo_name, io.BytesIO(cargo_bytes), "image/jpeg")},
            timeout=60
        )
        elapsed = time.time() - t0
        info(f"Response HTTP {resp.status_code} in {elapsed:.2f}s")
        if resp.status_code != 200:
            fail(f"Upload failed: {resp.status_code} — {resp.text[:300]}")
            results.append(("Cargo photo upload (HTTP)", False))
        else:
            payload = resp.json()
            ok(f"HTTP 200 received. success={payload.get('success')}")
            po_data = payload.get("po", {})
            meta    = po_data.get("partition_metadata") or {}
            returned_path = (
                meta.get("foto_carga_path")
                or (meta.get("logistics_checklist") or {}).get("foto_carga_path")
                or po_data.get("foto_carga_path")
            )
            if returned_path:
                ok(f"Response carries foto_carga_path: {returned_path}")
                results.append(("Cargo photo upload (HTTP)", True))
                results.append(("Cargo path in HTTP response", True))
            else:
                info(f"Full response po keys: {list(po_data.keys())}")
                info(f"partition_metadata: {json.dumps(meta, indent=2)[:400]}")
                fail("foto_carga_path missing from HTTP response payload")
                results.append(("Cargo photo upload (HTTP)", True))   # HTTP ok
                results.append(("Cargo path in HTTP response", False))
    except Exception as e:
        fail(f"Request error: {e}")
        results.append(("Cargo photo upload (HTTP)", False))

    # ── STEP 5: Upload receipt photo ───────────────────────────────────────────
    banner("STEP 5 · Upload Receipt Photo (foto_canhoto_path)")
    receipt_url   = f"{API_BASE}/kanban/pos/{test_po_id}/upload-receipt-photo"
    receipt_bytes, receipt_name = make_fake_image("test_canhoto_fake.jpg")
    try:
        info(f"POST → {receipt_url}")
        info(f"File  → {receipt_name} ({len(receipt_bytes)} bytes)")
        t0 = time.time()
        resp = requests.post(
            receipt_url,
            headers=headers,
            files={"file": (receipt_name, io.BytesIO(receipt_bytes), "image/jpeg")},
            timeout=60
        )
        elapsed = time.time() - t0
        info(f"Response HTTP {resp.status_code} in {elapsed:.2f}s")
        if resp.status_code != 200:
            fail(f"Upload failed: {resp.status_code} — {resp.text[:300]}")
            results.append(("Receipt photo upload (HTTP)", False))
        else:
            payload = resp.json()
            ok(f"HTTP 200 received. success={payload.get('success')}")
            po_data = payload.get("po", {})
            meta    = po_data.get("partition_metadata") or {}
            returned_path = (
                meta.get("foto_canhoto_path")
                or (meta.get("logistics_checklist") or {}).get("foto_canhoto_path")
                or po_data.get("foto_canhoto_path")
            )
            if returned_path:
                ok(f"Response carries foto_canhoto_path: {returned_path}")
                results.append(("Receipt photo upload (HTTP)", True))
                results.append(("Receipt path in HTTP response", True))
            else:
                info(f"partition_metadata: {json.dumps(meta, indent=2)[:400]}")
                fail("foto_canhoto_path missing from HTTP response payload")
                results.append(("Receipt photo upload (HTTP)", True))
                results.append(("Receipt path in HTTP response", False))
    except Exception as e:
        fail(f"Request error: {e}")
        results.append(("Receipt photo upload (HTTP)", False))

    # ── STEP 6: DB persistence verification ───────────────────────────────────
    banner("STEP 6 · Database Persistence Verification")
    try:
        # Re-read the row fresh from DB (no cache)
        cur.execute("""
            SELECT
                id,
                status_macro,
                partition_metadata,
                partition_metadata->>'foto_carga_path'    AS foto_carga,
                partition_metadata->>'foto_canhoto_path'  AS foto_canhoto,
                partition_metadata->'logistics_checklist'->>'foto_carga_path'   AS lc_cargo,
                partition_metadata->'logistics_checklist'->>'foto_canhoto_path' AS lc_canhoto
            FROM purchase_orders
            WHERE id = %s;
        """, (test_po_id,))
        row = cur.fetchone()
        if not row:
            fail(f"PO {test_po_id!r} not found in DB after upload!")
            results.append(("DB: foto_carga_path persisted", False))
            results.append(("DB: foto_canhoto_path persisted", False))
        else:
            _, _, _, foto_carga, foto_canhoto, lc_cargo, lc_canhoto = row
            # Accept value from root or logistics_checklist sub-key
            final_cargo   = foto_carga   or lc_cargo
            final_canhoto = foto_canhoto or lc_canhoto

            if final_cargo:
                ok(f"DB foto_carga_path   = {final_cargo}")
                results.append(("DB: foto_carga_path persisted", True))
            else:
                fail("DB foto_carga_path is NULL — not persisted!")
                results.append(("DB: foto_carga_path persisted", False))

            if final_canhoto:
                ok(f"DB foto_canhoto_path = {final_canhoto}")
                results.append(("DB: foto_canhoto_path persisted", True))
            else:
                fail("DB foto_canhoto_path is NULL — not persisted!")
                results.append(("DB: foto_canhoto_path persisted", False))

            # Full partition_metadata dump
            info("Full partition_metadata from DB:")
            meta_str = json.dumps(row[2], indent=2) if isinstance(row[2], dict) else str(row[2])
            for line in meta_str.split('\n')[:30]:
                print(f"      {line}")

    except Exception as e:
        fail(f"DB verification query failed: {e}")
        results.append(("DB: foto_carga_path persisted", False))
        results.append(("DB: foto_canhoto_path persisted", False))
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass

    # ── SUMMARY ───────────────────────────────────────────────────────────────
    _print_summary(results)


def _print_summary(results):
    banner("INTEGRATION TEST SUMMARY")
    all_pass = True
    for name, passed in results:
        if passed:
            ok(f"PASS  {name}")
        else:
            fail(f"FAIL  {name}")
            all_pass = False

    print()
    if all_pass:
        print(f"  {GREEN}{BOLD}🎉  ALL CHECKS PASSED — Upload persistence verified end-to-end.{RESET}")
    else:
        failed = [n for n, p in results if not p]
        print(f"  {RED}{BOLD}❌  {len(failed)} CHECK(S) FAILED: {', '.join(failed)}{RESET}")
    print()


if __name__ == "__main__":
    run()
