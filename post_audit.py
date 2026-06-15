FILE = 'C:/Documentos/BotCase/FlexFlow/frontend/src/pages/KanbanPage.jsx'
with open(FILE, 'rb') as f:
    raw = f.read()
lines = raw.split(b'\n')
print(f'Total lines: {len(lines)}\n')

needles = {
    'type="file"': b'type="file"',
    'LogisticsUploadSection': b'LogisticsUploadSection',
    'globalTruckInputRef': b'globalTruckInputRef',
    'globalReceiptInputRef': b'globalReceiptInputRef',
    'activeUploadPoIdRef (KanbanPage scope)': b'activeUploadPoIdRef',
    'truckInputRef (subcomp)': b'truckInputRef',
    'receiptInputRef (subcomp)': b'receiptInputRef',
    'activePoIdRef (subcomp)': b'activePoIdRef',
    'F12 TRACE': b'F12 TRACE',
    'handleEvidenceUpload': b'handleEvidenceUpload',
}

for label, needle in needles.items():
    hits = [i+1 for i, l in enumerate(lines) if needle in l]
    print(f'[{label}] -> {len(hits)} hit(s): {hits[:8]}')
