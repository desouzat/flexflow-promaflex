import re

FILE = 'C:/Documentos/BotCase/FlexFlow/frontend/src/pages/KanbanPage.jsx'
with open(FILE, 'rb') as f:
    data = f.read()

lines = data.split(b'\n')
print(f'Total lines: {len(lines)}\n')

patterns = [
    b'truckPhotoInputRef',
    b'receiptPhotoInputRef',
    b'globalTruckInputRef',
    b'globalReceiptInputRef',
]

for p in patterns:
    hits = [(i+1, lines[i].decode('utf-8','replace').strip()) for i in range(len(lines)) if p in lines[i]]
    print(f'[{p.decode()}] -> {len(hits)} hit(s):')
    for ln, content in hits:
        print(f'  L{ln}: {content[:120]}')
    print()
