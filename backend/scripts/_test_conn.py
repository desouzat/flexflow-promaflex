import psycopg2
import sys

print("Testing raw connection to 127.0.0.1:5434 with sslmode=disable...")
try:
    conn = psycopg2.connect(
        host="127.0.0.1",
        port=5434,
        dbname="flexflow_prod",
        user="flexflow_app",
        password="Souza@123",
        sslmode="disable",
        connect_timeout=10
    )
    print("SUCCESS — connected!")
    cur = conn.cursor()
    cur.execute("SELECT version()")
    print("PostgreSQL version:", cur.fetchone())
    cur.execute("SELECT current_user")
    print("Current user:", cur.fetchone())
    conn.close()
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)
