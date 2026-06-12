"""
run_e2e_with_server.py
======================
Orchestrator: boots Uvicorn in a subprocess, waits for it to be ready,
runs the upload integration test, then kills the server.
"""
import subprocess
import sys
import os
import time
import socket

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT    = os.path.dirname(os.path.abspath(__file__))           # project root
LOG     = os.path.join(ROOT, "uvicorn_e2e.log")
PORT    = 8001   # Use 8001 to avoid conflict with any existing process on 8000
TIMEOUT = 40   # seconds to wait for server startup

# ── Step 1: Kill any existing process on port 8001 ───────────────────────────
print("\n[ORCHESTRATOR] Killing any existing process on port 8001...")
subprocess.run(
    ["powershell", "-Command",
     f"$p = Get-NetTCPConnection -LocalPort {PORT} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique; if($p){{Stop-Process -Id $p -Force -ErrorAction SilentlyContinue}}"],
    cwd=ROOT, capture_output=True
)
time.sleep(1)

# ── Step 2: Launch Uvicorn as background subprocess ──────────────────────────
print(f"[ORCHESTRATOR] Starting uvicorn backend.main:app on port {PORT}...")
log_file = open(LOG, "w", encoding="utf-8")
server_proc = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "backend.main:app",
     "--port", str(PORT), "--log-level", "info"],
    cwd=ROOT,
    stdout=log_file,
    stderr=log_file,
    env={**os.environ, "PYTHONIOENCODING": "utf-8"}
)
print(f"[ORCHESTRATOR] Uvicorn PID: {server_proc.pid}")

# ── Step 3: Poll until port is accepting connections ─────────────────────────
print(f"[ORCHESTRATOR] Waiting for port {PORT} to open (max {TIMEOUT}s)...")
started = False
for i in range(TIMEOUT):
    time.sleep(1)
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=1):
            started = True
            print(f"[ORCHESTRATOR] Server is up after {i+1}s!")
            break
    except (ConnectionRefusedError, OSError):
        print(f"  [{i+1}s] still waiting...", flush=True)

if not started:
    print(f"[ORCHESTRATOR] ERROR: Server did not start within {TIMEOUT}s.")
    print("[ORCHESTRATOR] Boot log tail:")
    log_file.flush()
    with open(LOG, encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines[-20:]:
        print("  ", line, end="")
    server_proc.terminate()
    sys.exit(1)

# Extra buffer for FastAPI/SQLAlchemy init to complete
time.sleep(8)

# ── Step 4: Run the integration test ─────────────────────────────────────────
print("\n[ORCHESTRATOR] Running integration test harness...")
result = subprocess.run(
    [sys.executable, "-m", "backend.scripts.test_upload_integration"],
    cwd=ROOT,
    env={**os.environ, "PYTHONIOENCODING": "utf-8"}
)

# ── Step 5: Kill the server ───────────────────────────────────────────────────
print("\n[ORCHESTRATOR] Terminating uvicorn...")
server_proc.terminate()
try:
    server_proc.wait(timeout=5)
    print("[ORCHESTRATOR] Uvicorn terminated cleanly.")
except subprocess.TimeoutExpired:
    server_proc.kill()
    print("[ORCHESTRATOR] Uvicorn force-killed.")
log_file.close()

sys.exit(result.returncode)
