"""
Task 3: Update user display names in the 'users' table via Cloud SQL proxy (port 5434).
Run locally. Do NOT deploy.
"""
import sys
import psycopg2

# Windows encoding fix
if sys.platform == 'win32':
    import io as _io
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

DB_HOST = "localhost"
DB_PORT = 5435
DB_NAME = "flexflow"
DB_USER = "flexflow_app"
DB_PASS = "Souza@123"

# Exact mapping: email -> display name (ONET-style uppercase)
UPDATES = [
    ("clayton@promaflex.com.br",                  "CLAYTON ROGERIO"),
    ("alexandre@promaflex.com.br",                "ALEXANDRE RODRIGUES"),
    ("rodrigo.cruz@promaflex.com.br",             "RODRIGO ATANAZIO CRUZ"),
    ("psauma_promaflex@grupovelletri.com.br",      "PEDRO HENRIQUE R S REPRESENTACOES"),
    ("Luis.monteiro@promaflex.com.br",             "LUIZ MONTEIRO"),
    ("leandro@promaflex.com.br",                  "LEANDRO JOSE DE SOUZA"),
    ("fabio.sodre@promaflex.com.br",              "FABIO SODRE"),
    ("guilherme@promaflex.com.br",                "GUILHERME M VELHO"),
    ("isadora_promaflex@grupovelletri.com.br",     "ISADORA DE OLIVEIRA MOURA"),
    ("abimaelbrito@promaflex.com.br",             "ABIMAEL M DE BRITO SILVA"),
    ("douglas_promaflex@grupovelletri.com.br",     "DOUGLAS LUCIO"),
    ("alessandro.comercial74@gmail.com",           "ALESSANDRO MENDONCA COSTA"),
    ("julio.jotage@terra.com.br",                 "JULIO AUGUSTO GONZAGA"),
    ("raw.representacoes@gmail.com",              "RAUL"),
    ("cesar.promaflex@gmail.com",                 "CESAR KIYOSHI YOSHIMOTO"),
]

def main():
    print("=" * 70)
    print("  Task 3: Update user display names (production DB via port 5434)")
    print("=" * 70)
    print(f"  Connecting to {DB_HOST}:{DB_PORT}/{DB_NAME} as {DB_USER}")
    print()

    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS,
            connect_timeout=10,
        )
        conn.autocommit = False
        cur = conn.cursor()

        updated   = []
        not_found = []
        errors    = []

        for email, name in UPDATES:
            try:
                cur.execute(
                    "UPDATE users SET name = %s WHERE LOWER(email) = LOWER(%s)",
                    (name, email),
                )
                rows_affected = cur.rowcount
                if rows_affected > 0:
                    updated.append((email, name))
                    print(f"  ✅  [{rows_affected}] {email:50s} → {name}")
                else:
                    not_found.append(email)
                    print(f"  ⚠   NOT FOUND: {email}")
            except Exception as e:
                errors.append((email, str(e)))
                print(f"  ❌  ERROR for {email}: {e}")

        if errors:
            conn.rollback()
            print(f"\n  ❌ Rolled back — {len(errors)} error(s) encountered.")
        else:
            conn.commit()
            print(f"\n  ✅ Transaction committed.")

        cur.close()
        conn.close()

        print()
        print("=" * 70)
        print(f"  SUMMARY")
        print(f"  ✅ Updated      : {len(updated)}/{len(UPDATES)}")
        if not_found:
            print(f"  ⚠  Not found  : {len(not_found)}")
            for e in not_found:
                print(f"       {e}")
        if errors:
            print(f"  ❌ Errors      : {len(errors)}")
            for e, err in errors:
                print(f"       {e}: {err}")
        print("=" * 70)

        # Verify results
        if not errors:
            print("\n  Verification — reading back updated rows:")
            conn2 = psycopg2.connect(
                host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                user=DB_USER, password=DB_PASS, connect_timeout=10,
            )
            cur2 = conn2.cursor()
            emails = [e for e, _ in UPDATES]
            cur2.execute(
                "SELECT email, name FROM users WHERE LOWER(email) = ANY(%s) ORDER BY email",
                ([e.lower() for e in emails],)
            )
            rows = cur2.fetchall()
            for row_email, row_name in rows:
                print(f"    DB: {row_email:50s} | {row_name}")
            cur2.close()
            conn2.close()

    except psycopg2.OperationalError as e:
        print(f"  ❌ Cannot connect to database: {e}")
        print("     Is cloud-sql-proxy.exe running on port 5434?")
        sys.exit(1)

if __name__ == "__main__":
    main()
