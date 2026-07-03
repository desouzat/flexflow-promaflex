import psycopg2
import sys

# Probe what databases exist on port 5433 (local PostgreSQL)
CANDIDATES = [
    ("127.0.0.1", 5433, "postgres", "postgres", ""),
    ("127.0.0.1", 5433, "postgres", "postgres", "postgres"),
    ("127.0.0.1", 5433, "postgres", "thiago", ""),
    ("localhost", 5433, "postgres", "postgres", ""),
]

for host, port, dbname, user, password in CANDIDATES:
    try:
        kwargs = dict(host=host, port=port, dbname=dbname, user=user, connect_timeout=3)
        if password:
            kwargs["password"] = password
        conn = psycopg2.connect(**kwargs)
        cur = conn.cursor()
        cur.execute("SELECT datname FROM pg_database WHERE datname NOT IN ('template0','template1') ORDER BY datname")
        dbs = [r[0] for r in cur.fetchall()]
        print(f"Connected as {user}@{host}:{port}/{dbname}")
        print("  Databases:", dbs)
        cur.close()
        conn.close()
        break
    except Exception as e:
        print(f"  {user}@{host}:{port}/{dbname}: {e}")
