import sys, os, json
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.path.insert(0, r'C:\Documentos\BotCase\FlexFlow')
from backend.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Get full partition_metadata for the SHIPPING PO
    result = conn.execute(text("""
        SELECT po_number, status_macro, partition_metadata, updated_at
        FROM purchase_orders
        WHERE status_macro = 'SHIPPING'
        ORDER BY updated_at DESC
        LIMIT 3
    """))
    rows = result.fetchall()
    for r in rows:
        print(f"\n=== PO {r[0]} (status={r[1]}, updated={r[3]}) ===")
        if r[2]:
            print(json.dumps(r[2], indent=2, default=str))
        else:
            print("  partition_metadata IS NULL")

    # Also list ALL uploads directory content
    print("\n=== backend/uploads directory ===")
    import os as _os
    uploads = r'C:\Documentos\BotCase\FlexFlow\backend\uploads'
    for root, dirs, files in _os.walk(uploads):
        for f in files:
            full = _os.path.join(root, f)
            print(f"  {full} ({_os.path.getsize(full)} bytes)")
    if not list(_os.walk(uploads))[0][2] and not list(_os.walk(uploads))[0][1]:
        print("  (empty)")
