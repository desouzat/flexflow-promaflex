"""
Temporary production database audit script.
Run with: python scripts/db_audit.py
Target: localhost:5434 (Cloud SQL Auth Proxy)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from backend.database import SessionLocal

DIVIDER = "=" * 62


def audit():
    db = SessionLocal()
    try:
        print(DIVIDER)
        print("  PRODUCTION DATABASE STATE AUDIT")
        print("  Target : localhost:5434 (Cloud SQL Auth Proxy)")
        print(DIVIDER)

        # ── 1. Row counts ────────────────────────────────────────────────────
        print("\n[1] TABLE ROW COUNTS")
        table_queries = [
            ("users",          "SELECT COUNT(*) FROM users"),
            ("tenants",        "SELECT COUNT(*) FROM tenants"),
            ("GlobalConfig",   'SELECT COUNT(*) FROM "GlobalConfig"'),
            ("purchase_orders","SELECT COUNT(*) FROM purchase_orders"),
        ]
        counts = {}
        for table_name, sql in table_queries:
            try:
                count = db.execute(text(sql)).scalar()
                counts[table_name] = count
                status = "OK"
                print(f"  {table_name:<22}: {count:>5} rows  [{status}]")
            except Exception as exc:
                counts[table_name] = None
                print(f"  {table_name:<22}: ERROR - {exc}")

        # ── 2. Admin user verification ────────────────────────────────────────
        print("\n[2] USER VERIFICATION  (admin@botcase.com.br)")
        try:
            row = db.execute(
                text(
                    "SELECT id, email, role, area, is_active "
                    "FROM users WHERE email = 'admin@botcase.com.br'"
                )
            ).fetchone()
            if row:
                print("  Status   : FOUND")
                print(f"  id       : {row[0]}")
                print(f"  email    : {row[1]}")
                print(f"  role     : {row[2]}")
                print(f"  area     : {row[3]}")
                print(f"  is_active: {row[4]}")
            else:
                print("  Status   : NOT FOUND")
        except Exception as exc:
            print(f"  Status   : ERROR - {exc}")

        # ── 3. Summary + conditional seeding ─────────────────────────────────
        print("\n[3] AUDIT SUMMARY")
        user_count = counts.get("users")

        if user_count is None:
            print("  users table  : TABLE NOT ACCESSIBLE")
            print("  seeding      : SKIPPED (fix table error first)")
        elif user_count == 0:
            print("  users table  : EMPTY — database is blank")
            print("  seeding      : REQUIRED — triggering now...")
            print(DIVIDER)
            _trigger_seed(db)
        else:
            print(f"  users table  : POPULATED ({user_count} users)")
            print("  seeding      : NOT REQUIRED")

        print(DIVIDER)

    finally:
        db.close()


def _trigger_seed(parent_db):
    """Close the audit session and run the official seed script, then re-query."""
    parent_db.close()

    # Import and run the seed function directly (avoids subprocess encoding issues)
    import importlib.util, pathlib

    seed_path = pathlib.Path(__file__).parent / "seed_official_users.py"
    spec = importlib.util.spec_from_file_location("seed_official_users", seed_path)
    seed_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed_mod)
    seed_mod.seed_users()

    # Re-query counts after seeding
    print("\n[4] POST-SEED VERIFICATION")
    db2 = SessionLocal()
    try:
        for table_name, sql in [
            ("users",      "SELECT COUNT(*) FROM users"),
            ("tenants",    "SELECT COUNT(*) FROM tenants"),
            ("GlobalConfig", 'SELECT COUNT(*) FROM "GlobalConfig"'),
        ]:
            try:
                count = db2.execute(text(sql)).scalar()
                print(f"  {table_name:<22}: {count:>5} rows")
            except Exception as exc:
                print(f"  {table_name:<22}: ERROR - {exc}")

        # Re-verify admin
        row = db2.execute(
            text(
                "SELECT id, role, is_active FROM users "
                "WHERE email = 'admin@botcase.com.br'"
            )
        ).fetchone()
        if row:
            print(f"\n  admin@botcase.com.br : CONFIRMED IN DB")
            print(f"    id        = {row[0]}")
            print(f"    role      = {row[1]}")
            print(f"    is_active = {row[2]}")
        else:
            print("\n  admin@botcase.com.br : STILL NOT FOUND AFTER SEED — investigate!")
    finally:
        db2.close()


if __name__ == "__main__":
    audit()
