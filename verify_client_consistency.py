"""
Quick verification script to check client consistency per PO
"""
import pandas as pd
import sys
import io

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

df = pd.read_excel('onet_production_test_50_rows.xlsx')

print('=' * 80)
print('CLIENT CONSISTENCY VERIFICATION')
print('=' * 80)
print()

all_consistent = True
inconsistent_pos = []

for po in df['Pedido'].unique():
    po_data = df[df['Pedido'] == po]
    clients = po_data['Cliente'].unique()
    sellers = po_data['Vendedor'].unique()
    payment_terms = po_data['Condição Pagamento'].unique()
    
    is_consistent = len(clients) == 1 and len(sellers) == 1 and len(payment_terms) == 1
    
    if not is_consistent:
        all_consistent = False
        inconsistent_pos.append(po)
    
    status = '[OK] CONSISTENT' if is_consistent else '[ERROR] INCONSISTENT'
    print(f'PO: {po}')
    print(f'  Items: {len(po_data)}')
    print(f'  Unique Clients: {len(clients)} - {clients[0] if len(clients) == 1 else "MULTIPLE!"}')
    print(f'  Unique Sellers: {len(sellers)} - {sellers[0] if len(sellers) == 1 else "MULTIPLE!"}')
    print(f'  Unique Payment Terms: {len(payment_terms)} - {payment_terms[0] if len(payment_terms) == 1 else "MULTIPLE!"}')
    print(f'  Status: {status}')
    print()

print('=' * 80)
print('SUMMARY')
print('=' * 80)
print(f'Total POs: {df["Pedido"].nunique()}')
print(f'Total Items: {len(df)}')
print(f'Consistent POs: {df["Pedido"].nunique() - len(inconsistent_pos)}')
print(f'Inconsistent POs: {len(inconsistent_pos)}')
print()
if all_consistent:
    print('[OK] ALL POs HAVE CONSISTENT CLIENT, SELLER, AND PAYMENT TERMS!')
else:
    print(f'[ERROR] Found {len(inconsistent_pos)} inconsistent POs: {inconsistent_pos}')
print('=' * 80)
