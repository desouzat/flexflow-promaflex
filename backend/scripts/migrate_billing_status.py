"""
FF-HARDENING-012.2 — Database Migration Script
migrate_billing_status.py

Purpose:
    Alter the 'check_po_status_macro' CheckConstraint on the purchase_orders
    table to accept the new 'BILLING' status value (Faturamento stage).

Usage:
    Ensure the Cloud SQL Auth Proxy is running on localhost:5434, then run:

        python backend/scripts/migrate_billing_status.py

    The script loads credentials from backend/.env automatically.

Security:
    This is a LOCAL, standalone script. It is NOT exposed as a REST endpoint.
    It must be run manually by a developer with DB access.
"""
import os
import sys

# ── Load environment variables from backend/.env ──────────────────────────────
try:
    from dotenv import load_dotenv
    # scripts/ lives inside backend/, so backend/.env is one level up
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(dotenv_path=os.path.abspath(env_path))
    print("[migrate_billing_status] Loaded backend/.env file.")
except ImportError:
    print("[migrate_billing_status] python-dotenv not found — using existing environment variables.")

import psycopg2

# ── Build connection string ───────────────────────────────────────────────────
DB_HOST     = os.getenv("DB_HOST", "localhost")
DB_PORT     = os.getenv("DB_PORT", "5434")          # Cloud SQL Auth Proxy default
DB_NAME     = os.getenv("DB_NAME") or os.getenv("POSTGRES_DB", "flexflow")
DB_USER     = os.getenv("DB_USER") or os.getenv("POSTGRES_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD") or os.getenv("POSTGRES_PASSWORD", "")

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgresql"):
    import urllib.parse
    parsed = urllib.parse.urlparse(DATABASE_URL)
    DB_HOST     = parsed.hostname or DB_HOST
    DB_PORT     = str(parsed.port or 5434)
    DB_NAME     = parsed.path.lstrip("/") or DB_NAME
    DB_USER     = parsed.username or DB_USER
    DB_PASSWORD = urllib.parse.unquote(parsed.password) if parsed.password else DB_PASSWORD

print(f"[migrate_billing_status] Connecting to {DB_HOST}:{DB_PORT}/{DB_NAME} as {DB_USER}...")

# ── Valid statuses after the migration ───────────────────────────────────────
# NOTE: This list must exactly match VALID_STATUSES in backend/models.py
VALID_STATUSES_AFTER = [
    "DRAFT",
    "SUBMITTED",
    "APPROVED",
    "MANUFACTURING",
    "BILLING",          # << NEW (Faturamento stage, FF-HARDENING-012.2)
    "SHIPPING",
    "FINANCE",
    "COMPLETED",
    "CANCELLED",
    "WAITING_COMMERCIAL_PARTITION",
    "ANALISE_CREDITO",
    "ARCHIVED",
    "ARCHIVED_PARTITIONED",
    "WAITING_MATERIAL",
]

STATUS_TUPLE = "(" + ", ".join(f"'{s}'" for s in VALID_STATUSES_AFTER) + ")"

# ── Migration SQL ─────────────────────────────────────────────────────────────
SQL_STEPS = [
    (
        "Drop old check_po_status_macro constraint",
        "ALTER TABLE purchase_orders DROP CONSTRAINT IF EXISTS check_po_status_macro;"
    ),
    (
        "Add new check_po_status_macro constraint with BILLING",
        f"ALTER TABLE purchase_orders ADD CONSTRAINT check_po_status_macro "
        f"CHECK (status_macro IN {STATUS_TUPLE});"
    ),
]


def run_migration():
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=int(DB_PORT),
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        conn.autocommit = False
        cur = conn.cursor()

        print("\n[migrate_billing_status] Starting migration...\n")

        for step_name, sql in SQL_STEPS:
            print(f"  >> {step_name}...")
            print(f"     SQL: {sql}")
            cur.execute(sql)
            print(f"     Done.\n")

        conn.commit()
        print("[migrate_billing_status] Migration committed successfully.")
        print(f"[migrate_billing_status] BILLING is now a valid status_macro value.")

    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        print(f"\n[migrate_billing_status] Migration FAILED: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    run_migration()
