"""
deep_audit.py — counts all upload-related strings and prints context blocks
"""
FILE = 'C:/Documentos/BotCase/FlexFlow/frontend/src/pages/KanbanPage.jsx'

with open(FILE, 'rb') as f:
    raw = f.read()

lines = raw.split(b'\n')
total = len(lines)
print(f'Total lines: {total}\n')

needles = [
    b'UPLOAD DE EVID',
    b'Foto da Carga Carregada',
    b'Nota Fiscal com Canhoto Assinado',
    b'foto_carga',
    b'foto_canhoto',
    b'handleEvidenceUpload',
    b'logisticsChecklist',
    b'globalTruckInputRef',
    b'globalReceiptInputRef',
    b'activeUploadPoIdRef',
    b'type="file"',
    b"type='file'",
]

for needle in needles:
    hits = [i+1 for i, l in enumerate(lines) if needle in l]
    label = needle.decode('utf-8', 'replace')
    if hits:
        print(f'[{label}] -> {len(hits)} line(s): {hits}')
    else:
        print(f'[{label}] -> 0 hits')

print('\n--- FIRST 30 LINES ---')
for i, l in enumerate(lines[:30]):
    print(f'{i+1}: {l.decode("utf-8","replace").rstrip()}')

print('\n--- LAST 20 LINES ---')
for i, l in enumerate(lines[-20:]):
    print(f'{total-20+i+1}: {l.decode("utf-8","replace").rstrip()}')
