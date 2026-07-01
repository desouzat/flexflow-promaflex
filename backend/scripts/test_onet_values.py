"""
backend/scripts/test_onet_values.py
====================================
Standalone integration test that:
  1. Scans the workspace for any .xlsx file (or uses a path argument)
  2. Runs it through ImportService.validate_import_data()
  3. Prints the resulting JSON showing order_date, codigo_estruturado, carrier_name
  4. Queries the database for the first matching PO to prove DB persistence

Usage:
    python backend/scripts/test_onet_values.py [optional_path_to.xlsx]

If no path is given it searches the workspace for the most recent .xlsx file.
"""

import sys
import os
import json
import glob

# ── resolve project root so backend package is importable ────────────────────
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.services.import_service import ImportService
from backend.schemas.import_schema import ImportMapping, ColumnMapping, ImportFieldType, ImportRequest

# ── ONET final production schema column mapping ──────────────────────────────
ONET_MAPPINGS = [
    ColumnMapping(column_name="Nº do Pedido",       field_type=ImportFieldType.PO_NUMBER),
    ColumnMapping(column_name="Cliente",             field_type=ImportFieldType.CLIENT_NAME),
    ColumnMapping(column_name="Id Produto",          field_type=ImportFieldType.SKU),
    ColumnMapping(column_name="Qtd",                 field_type=ImportFieldType.QUANTITY),
    ColumnMapping(column_name="Produto",             field_type=ImportFieldType.DESCRIPTION),
    ColumnMapping(column_name="Unidade",             field_type=ImportFieldType.UNIT),
    ColumnMapping(column_name="Largura",             field_type=ImportFieldType.WIDTH),
    ColumnMapping(column_name="Comprimento",         field_type=ImportFieldType.LENGTH),
    ColumnMapping(column_name="Lead Time",           field_type=ImportFieldType.LEAD_TIME),
    ColumnMapping(column_name="Dt.Entrega",          field_type=ImportFieldType.DELIVERY_DATE),
    ColumnMapping(column_name="Dt.Faturamento",      field_type=ImportFieldType.BILLING_DATE),
    ColumnMapping(column_name="Data do Pedido",      field_type=ImportFieldType.ORDER_DATE),
    ColumnMapping(column_name="% ICMS",              field_type=ImportFieldType.ICMS_PERCENT),
    ColumnMapping(column_name="Bloqueio Faturamento",field_type=ImportFieldType.BLOCK_STATUS),
    ColumnMapping(column_name="Saldo",               field_type=ImportFieldType.BALANCE),
    ColumnMapping(column_name="Atraso",              field_type=ImportFieldType.DELAY),
    ColumnMapping(column_name="Cond.Pgto",           field_type=ImportFieldType.PAYMENT_TERMS),
    ColumnMapping(column_name="Frete",               field_type=ImportFieldType.FREIGHT),
    ColumnMapping(column_name="Vendedor",            field_type=ImportFieldType.SALESPERSON),
    ColumnMapping(column_name="IPI",                 field_type=ImportFieldType.IPI),
    ColumnMapping(column_name="VlUnit",              field_type=ImportFieldType.UNIT_VALUE),
    ColumnMapping(column_name="Total Item",          field_type=ImportFieldType.ITEM_TOTAL_VALUE),
    ColumnMapping(column_name="Vl.Pedido",           field_type=ImportFieldType.PO_TOTAL_VALUE),
    ColumnMapping(column_name="Codigo Estruturado",  field_type=ImportFieldType.CODIGO_ESTRUTURADO),
    ColumnMapping(column_name="Cod. Transportadora", field_type=ImportFieldType.CARRIER_CODE),
    ColumnMapping(column_name="Nome Transportadora", field_type=ImportFieldType.CARRIER_NAME),
]

MAPPING = ImportMapping(mappings=ONET_MAPPINGS)

TENANT_ID = "00000000-0000-0000-0000-000000000001"
USER_ID   = "00000000-0000-0000-0000-000000000002"


def find_xlsx():
    """Return the most recently modified .xlsx in the workspace."""
    files = glob.glob(os.path.join(ROOT, '**', '*.xlsx'), recursive=True)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def sep(title=""):
    print("\n" + "─" * 60)
    if title:
        print(f"  {title}")
        print("─" * 60)


def main():
    # ── resolve xlsx path ─────────────────────────────────────────────────────
    if len(sys.argv) > 1:
        xlsx_path = sys.argv[1]
    else:
        xlsx_path = find_xlsx()

    if not xlsx_path or not os.path.exists(xlsx_path):
        print("❌  No .xlsx file found. Pass a path as argument or place a file in the workspace.")
        sys.exit(1)

    sep("ONET VALUES INTEGRATION TEST")
    print(f"  File: {os.path.basename(xlsx_path)}")
    print(f"  Path: {xlsx_path}")

    # ── parse file ────────────────────────────────────────────────────────────
    with open(xlsx_path, 'rb') as f:
        content = f.read()

    request = ImportRequest(
        file_content=content,
        file_name=os.path.basename(xlsx_path),
        mapping=MAPPING,
        tenant_id=TENANT_ID,
        user_id=USER_ID
    )

    # ── mock DB so client-preference lookup returns None (no live DB needed) ─
    class _MockResult:
        def scalar_one_or_none(self): return None
    class _MockDB:
        def execute(self, *a, **kw): return _MockResult()

    svc = ImportService(db=_MockDB())  # no live DB needed for parsing stage
    response = svc.import_po(request)

    if not response.success:
        print(f"\n❌  Parse failed: {response.message}")
        sys.exit(1)

    # ── collect all POs (multi-PO support) ───────────────────────────────────
    po_list = getattr(response, 'po_list', None) or []
    if not po_list and response.items:
        # legacy single-PO response
        from backend.schemas.import_schema import ImportPOData
        synthetic = ImportPOData(
            po_number=response.po_number or "UNKNOWN",
            client_name=response.client_name or "",
            items=response.items
        )
        po_list = [synthetic]

    sep(f"PARSE RESULT  — {len(po_list)} PO(s) found")

    def get_items(po_obj):
        """Get items from a po object — which is a plain dict from import_po."""
        if isinstance(po_obj, dict):
            return po_obj.get('items', []) or []
        # Pydantic model: access via __dict__ or attribute
        val = po_obj.__dict__.get('items') if hasattr(po_obj, '__dict__') else None
        if val is not None:
            return val
        val = getattr(po_obj, 'items', None)
        if isinstance(val, list):
            return val
        return []

    def get_field(obj, field):
        """Get a field from either a dict or an object with attributes."""
        if isinstance(obj, dict):
            return obj.get(field)
        return getattr(obj, field, None)

    total_items = sum(len(get_items(p)) for p in po_list)
    print(f"  Total items across all POs: {total_items}")

    # ── inspect first PO ─────────────────────────────────────────────────────
    first_po = po_list[0]
    po_number   = get_field(first_po, 'po_number')   or '?'
    client_name = get_field(first_po, 'client_name') or '?'
    sep(f"FIRST PO: {po_number}  |  Client: {client_name}")

    # ── probe new fields from first 3 items ──────────────────────────────────
    FIELDS = ['order_date', 'codigo_estruturado', 'carrier_code', 'carrier_name',
              'delivery_date', 'billing_date', 'description', 'sku']

    found_order_date   = False
    found_codigo       = False
    found_carrier_name = False

    items = get_items(first_po)
    for idx, item in enumerate(items[:5]):
        sku = get_field(item, 'sku') or '?'
        sep(f"  Item {idx+1}: SKU={sku}")
        row = {}
        for f in FIELDS:
            val = get_field(item, f)
            row[f] = val
            if f == 'order_date'         and val: found_order_date   = True
            if f == 'codigo_estruturado' and val: found_codigo       = True
            if f == 'carrier_name'       and val: found_carrier_name = True
        print(json.dumps(row, ensure_ascii=False, indent=4, default=str))

    # ── proof summary ─────────────────────────────────────────────────────────
    sep("PROOF SUMMARY")
    def check(label, ok):
        icon = "✅" if ok else "❌"
        status = "POPULATED" if ok else "MISSING / NULL"
        print(f"  {icon}  {label}: {status}")

    check("order_date",         found_order_date)
    check("codigo_estruturado", found_codigo)
    check("carrier_name",       found_carrier_name)

    # ── db probe (optional — only if env + DB available) ─────────────────────
    sep("DATABASE PROBE (skip if DB offline)")
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(ROOT, '.env'))
        db_url = os.environ.get('DATABASE_URL', '')
        if not db_url:
            print("  ⚠️  DATABASE_URL not set — skipping DB probe.")
        else:
            from sqlalchemy import create_engine, text
            from sqlalchemy.pool import NullPool
            engine = create_engine(db_url, poolclass=NullPool)
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT po_number,
                           partition_metadata->>'order_date'    AS order_date,
                           partition_metadata->>'carrier_name'  AS carrier_name,
                           partition_metadata->>'carrier_code'  AS carrier_code
                    FROM purchase_orders
                    ORDER BY created_at DESC
                    LIMIT 5
                """))
                rows = result.fetchall()
                if not rows:
                    print("  ⚠️  No POs found in database.")
                else:
                    print(f"  {'PO Number':<20} {'order_date':<15} {'carrier_name':<30} {'carrier_code'}")
                    print(f"  {'-'*20} {'-'*15} {'-'*30} {'-'*15}")
                    for row in rows:
                        print(f"  {str(row[0] or ''):<20} {str(row[1] or ''):<15} {str(row[2] or ''):<30} {str(row[3] or '')}")

                # Also check items for codigo_estruturado
                result2 = conn.execute(text("""
                    SELECT oi.sku,
                           oi.extra_metadata->>'codigo_estruturado' AS codigo_estruturado,
                           oi.extra_metadata->>'order_date'          AS order_date
                    FROM order_items oi
                    JOIN purchase_orders po ON po.id = oi.po_id
                    ORDER BY oi.created_at DESC
                    LIMIT 5
                """))
                rows2 = result2.fetchall()
                if rows2:
                    print(f"\n  {'SKU':<20} {'codigo_estruturado':<25} {'order_date'}")
                    print(f"  {'-'*20} {'-'*25} {'-'*15}")
                    for row in rows2:
                        print(f"  {str(row[0] or ''):<20} {str(row[1] or ''):<25} {str(row[2] or '')}")

    except Exception as e:
        print(f"  ⚠️  DB probe skipped: {e}")

    sep("TEST COMPLETE")
    all_ok = found_order_date and found_codigo and found_carrier_name
    if all_ok:
        print("  ✅  ALL THREE KEY FIELDS SUCCESSFULLY POPULATED IN PARSER OUTPUT")
    else:
        print("  ❌  ONE OR MORE FIELDS NOT POPULATED — check import_service.py alias matching")
    print()

    sys.exit(0 if all_ok else 1)


if __name__ == '__main__':
    main()
