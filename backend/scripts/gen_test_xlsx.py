"""Generate a minimal ONET final-production-schema test spreadsheet."""
import openpyxl, sys, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'backend', 'scripts', 'onet_test_final_schema.xlsx')

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "ONET"

headers = [
    'N\u00ba do Pedido', 'Cliente', 'Id Produto', 'Qtd', 'Produto',
    'Unidade', 'Largura', 'Comprimento', 'Lead Time',
    'Dt.Entrega', 'Dt.Faturamento', 'Data do Pedido',
    '% ICMS', 'Bloqueio Faturamento', 'Saldo', 'Atraso',
    'Cond.Pgto', 'Frete', 'Vendedor', 'IPI',
    'VlUnit', 'Total Item', 'Vl.Pedido',
    'Codigo Estruturado', 'Cod. Transportadora', 'Nome Transportadora',
]
ws.append(headers)

rows = [
    ['70001', 'CLIENTE TESTE LTDA', 'SKU-001', 10, 'Perfil Metalico 6m',
     'UN', 100, 6000, 15,
     '25/07/2026', '30/07/2026', '01/06/2026',
     12.0, 'LIBERADO', 0, 0,
     '30 DDL', 500.00, 'Joao Silva', 0,
     250.00, 2500.00, 4000.00,
     'CE-0001-A', 'TRP01', 'Transportes Brasil Ltda'],
    ['70001', 'CLIENTE TESTE LTDA', 'SKU-002', 5, 'Chapa Galvanizada 2mm',
     'UN', 200, 2000, 20,
     '25/07/2026', '30/07/2026', '01/06/2026',
     12.0, 'LIBERADO', 0, 0,
     '30 DDL', 250.00, 'Joao Silva', 0,
     300.00, 1500.00, 4000.00,
     'CE-0002-B', 'TRP01', 'Transportes Brasil Ltda'],
    ['70002', 'OUTRO CLIENTE SA', 'SKU-010', 20, 'Barra Chata 3/16',
     'UN', 38, 6000, 10,
     '10/08/2026', '15/08/2026', '15/06/2026',
     7.0, 'LIBERADO', 0, 0,
     '28 DDL', 300.00, 'Maria Costa', 50.00,
     180.00, 3600.00, 3600.00,
     'CE-0010-X', 'TRP02', 'LOG Express SA'],
]

for row in rows:
    ws.append(row)

wb.save(OUT)
print(f"Generated: {OUT}")
print(f"Columns: {len(headers)}, Rows: {len(rows)}")
