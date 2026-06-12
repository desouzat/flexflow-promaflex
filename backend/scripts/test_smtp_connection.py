#!/usr/bin/env python3
"""
FlexFlow — SMTP Connection Test Harness
========================================
Standalone script to validate production SMTP credentials and connectivity
against the real mail server before going live.

Usage (from the workspace root):
    python backend/scripts/test_smtp_connection.py

The script will:
1. Load .env from backend/.env (same path used by the application)
2. Print the resolved SMTP configuration (password masked)
3. Attempt a real SMTP connection with the configured security mode
4. Send a test email to admin@botcase.com.br
5. Exit 0 on success, 1 on failure

Required .env variables (no defaults will work for a real send):
    SMTP_HOST    e.g. smtp.gmail.com
    SMTP_PORT    587 (STARTTLS) or 465 (SSL)
    SMTP_USER    e.g. noreply@botcase.com.br
    SMTP_PASS    App password or SMTP password
    SMTP_SENDER  (optional) Display name/address — falls back to SMTP_USER

DO NOT set SMTP_SIMULATE=true when running this script — it would bypass the
real send and always return success regardless of credentials.
"""

import os
import sys
import io
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

# ── Windows console UTF-8 fix ─────────────────────────────────────────────────
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# ── Load .env from backend/ directory ─────────────────────────────────────────
# We locate .env relative to this script file:  backend/scripts/ → backend/
BACKEND_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BACKEND_DIR / ".env"

try:
    from dotenv import load_dotenv
    if ENV_PATH.exists():
        load_dotenv(dotenv_path=ENV_PATH)
        print(f"✅ Loaded .env from: {ENV_PATH}")
    else:
        print(f"⚠️  .env file not found at {ENV_PATH} — using existing environment variables only.")
except ImportError:
    print("⚠️  python-dotenv not installed — relying on existing environment variables.")

# ── Resolve configuration ──────────────────────────────────────────────────────
SMTP_HOST     = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT_STR = os.getenv("SMTP_PORT", "587")
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASS     = os.getenv("SMTP_PASS", "")
SMTP_SENDER   = os.getenv("SMTP_SENDER", SMTP_USER)
TEST_RECIPIENT = "admin@botcase.com.br"
TIMEOUT_SECONDS = 10

try:
    SMTP_PORT = int(SMTP_PORT_STR)
except ValueError:
    print(f"❌ Invalid SMTP_PORT='{SMTP_PORT_STR}' — must be an integer (587 or 465).")
    sys.exit(1)

# ── Print resolved config ──────────────────────────────────────────────────────
print()
print("=" * 60)
print("FlexFlow — SMTP Connection Test Harness")
print("=" * 60)
print(f"  SMTP_HOST   : {SMTP_HOST}")
print(f"  SMTP_PORT   : {SMTP_PORT}  ({'SSL' if SMTP_PORT == 465 else 'STARTTLS'})")
print(f"  SMTP_USER   : {SMTP_USER or '(NOT SET)'}")
print(f"  SMTP_PASS   : {'*' * len(SMTP_PASS) if SMTP_PASS else '(NOT SET)'}")
print(f"  SMTP_SENDER : {SMTP_SENDER or '(defaults to SMTP_USER)'}")
print(f"  Recipient   : {TEST_RECIPIENT}")
print(f"  Timeout     : {TIMEOUT_SECONDS}s")
print("=" * 60)
print()

# ── Validate credentials ───────────────────────────────────────────────────────
if not SMTP_USER:
    print("❌ SMTP_USER is not set. Please configure it in backend/.env")
    sys.exit(1)

if not SMTP_PASS:
    print("❌ SMTP_PASS is not set. Please configure it in backend/.env")
    sys.exit(1)

# ── Build test email ───────────────────────────────────────────────────────────
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
subject = f"[FlexFlow SMTP Test] Connection Validated at {timestamp}"

body = f"""\
This is an automated SMTP connectivity test sent by the FlexFlow
production readiness harness.

Timestamp   : {timestamp}
SMTP Host   : {SMTP_HOST}:{SMTP_PORT}
Security    : {'SSL (port 465)' if SMTP_PORT == 465 else 'STARTTLS (port 587)'}
Sender      : {SMTP_SENDER}
Recipient   : {TEST_RECIPIENT}

If you received this email, the SMTP configuration is working correctly
and the FlexFlow support ticket system is ready to send real notifications.

—
FlexFlow Infrastructure | BotCase
"""

msg = MIMEMultipart()
msg["From"]    = SMTP_SENDER
msg["To"]      = TEST_RECIPIENT
msg["Subject"] = subject
msg.attach(MIMEText(body, "plain", "utf-8"))

# ── Attempt real SMTP connection ───────────────────────────────────────────────
server = None
success = False

try:
    if SMTP_PORT == 465:
        print(f"[1/4] Connecting via smtplib.SMTP_SSL to {SMTP_HOST}:{SMTP_PORT} (timeout={TIMEOUT_SECONDS}s)...")
        server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=TIMEOUT_SECONDS)
        print("      ✅ SSL connection established.")
    else:
        print(f"[1/4] Connecting via smtplib.SMTP to {SMTP_HOST}:{SMTP_PORT} (timeout={TIMEOUT_SECONDS}s)...")
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=TIMEOUT_SECONDS)
        print("      ✅ Plain connection established.")

        print("[2/4] Sending EHLO...")
        server.ehlo()
        print("      ✅ EHLO accepted.")

        print("[3/4] Upgrading to STARTTLS...")
        server.starttls()
        server.ehlo()  # Re-identify after upgrade
        print("      ✅ STARTTLS upgrade successful.")

    step = "[2/4]" if SMTP_PORT == 465 else "[4/4]"
    print(f"{step} Authenticating as {SMTP_USER}...")
    server.login(SMTP_USER, SMTP_PASS)
    print(f"      ✅ Login successful.")

    print(f"\n📧 Sending test email to {TEST_RECIPIENT}...")
    server.sendmail(SMTP_SENDER, [TEST_RECIPIENT], msg.as_string())
    print(f"   ✅ Email accepted by {SMTP_HOST} for delivery.")
    success = True

except smtplib.SMTPAuthenticationError as e:
    print(f"\n❌ AUTHENTICATION FAILED for '{SMTP_USER}'.")
    print(f"   Detail: {e}")
    print()
    print("   Troubleshooting tips:")
    print("   • For Gmail: ensure you are using an App Password (not your account password).")
    print("     Generate one at: https://myaccount.google.com/apppasswords")
    print("   • For other providers: verify SMTP_USER and SMTP_PASS are correct.")

except smtplib.SMTPConnectError as e:
    print(f"\n❌ CONNECTION REFUSED to {SMTP_HOST}:{SMTP_PORT}.")
    print(f"   Detail: {e}")
    print()
    print("   Troubleshooting tips:")
    print("   • Verify SMTP_HOST and SMTP_PORT are correct.")
    print("   • Check if a firewall or proxy is blocking outbound SMTP traffic.")
    print("   • Try SMTP_PORT=465 (SSL) if 587 (STARTTLS) is blocked.")

except smtplib.SMTPRecipientsRefused as e:
    print(f"\n❌ RECIPIENT REFUSED: {TEST_RECIPIENT}")
    print(f"   Detail: {e}")

except TimeoutError:
    print(f"\n❌ CONNECTION TIMEOUT after {TIMEOUT_SECONDS}s connecting to {SMTP_HOST}:{SMTP_PORT}.")
    print("   The server is unreachable or the network is blocking the connection.")

except ConnectionRefusedError as e:
    print(f"\n❌ CONNECTION REFUSED — port {SMTP_PORT} is not open on {SMTP_HOST}.")
    print(f"   Detail: {e}")

except OSError as e:
    # Catches socket.gaierror (DNS failure) and similar OS-level errors
    print(f"\n❌ NETWORK ERROR: {type(e).__name__}: {e}")
    print(f"   Cannot resolve or reach host '{SMTP_HOST}'.")
    print("   Check SMTP_HOST spelling and DNS/internet connectivity.")

except Exception as e:
    print(f"\n❌ UNEXPECTED ERROR: {type(e).__name__}: {e}")

finally:
    if server is not None:
        try:
            server.quit()
            print("   [SMTP] Session closed cleanly via QUIT.")
        except Exception:
            pass

# ── Final result ───────────────────────────────────────────────────────────────
print()
print("=" * 60)
if success:
    print("🎉 SMTP TEST PASSED — email delivered successfully.")
    print(f"   Check inbox at: {TEST_RECIPIENT}")
    print("=" * 60)
    sys.exit(0)
else:
    print("❌ SMTP TEST FAILED — see errors above.")
    print("   The FlexFlow application will fall back to console logging")
    print("   for ticket notifications until SMTP is correctly configured.")
    print("=" * 60)
    sys.exit(1)
