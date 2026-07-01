"""Debug script to inspect po_list structure."""
import sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from backend.services.import_service import ImportService
from backend.schemas.import_schema import ImportMapping, ColumnMapping, ImportFieldType, ImportRequest

MAPPINGS = [
    ColumnMapping(column_name="Nº do Pedido",       field_type=ImportFieldType.PO_NUMBER),
    ColumnMapping(column_name="Cliente",             field_type=ImportFieldType.CLIENT_NAME),
    ColumnMapping(column_name="Id Produto",          field_type=ImportFieldType.SKU),
    ColumnMapping(column_name="Qtd",                 field_type=ImportFieldType.QUANTITY),
    ColumnMapping(column_name="Produto",             field_type=ImportFieldType.DESCRIPTION),
    ColumnMapping(column_name="Data do Pedido",      field_type=ImportFieldType.ORDER_DATE),
    ColumnMapping(column_name="Dt.Faturamento",      field_type=ImportFieldType.BILLING_DATE),
    ColumnMapping(column_name="Codigo Estruturado",  field_type=ImportFieldType.CODIGO_ESTRUTURADO),
    ColumnMapping(column_name="Nome Transportadora", field_type=ImportFieldType.CARRIER_NAME),
]
MAPPING = ImportMapping(mappings=MAPPINGS)

class _MockResult:
    def scalar_one_or_none(self): return None
class _MockDB:
    def execute(self, *a, **kw): return _MockResult()

xlsx = os.path.join(ROOT, 'backend', 'scripts', 'onet_test_final_schema.xlsx')
with open(xlsx, 'rb') as f:
    content = f.read()

req = ImportRequest(
    file_content=content,
    file_name='onet_test_final_schema.xlsx',
    mapping=MAPPING,
    tenant_id="00000000-0000-0000-0000-000000000001",
    user_id="00000000-0000-0000-0000-000000000002"
)

svc = ImportService(db=_MockDB())
resp = svc.import_po(req)

print("success:", resp.success)
print("type(po_list):", type(getattr(resp, 'po_list', None)))
po_list = getattr(resp, 'po_list', None) or []
if po_list:
    po = po_list[0]
    print("type(po):", type(po))
    print("dir(po):", [x for x in dir(po) if not x.startswith('_')])
    # access items directly
    items_attr = po.__class__.__dict__.get('items')
    print("items_attr from __dict__:", items_attr)
    # try model_fields
    if hasattr(po, 'model_fields'):
        print("model_fields:", list(po.model_fields.keys()))
    # raw access
    raw_items = po.__dict__.get('items') if hasattr(po, '__dict__') else None
    print("po.__dict__.get('items'):", type(raw_items), raw_items[:2] if raw_items else None)
