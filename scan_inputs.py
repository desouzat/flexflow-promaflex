import sys
FILE = 'C:/Documentos/BotCase/FlexFlow/frontend/src/pages/KanbanPage.jsx'
with open(FILE, 'rb') as f:
    data = f.read()

lines = data.split(b'\n')
print(f'Total lines: {len(lines)}')

hits = []
for i, line in enumerate(lines):
    ll = line.lower()
    if b'type="file"' in line or b"type='file'" in line:
        hits.append((i+1, 'FILE_INPUT', line.decode('utf-8','replace').strip()))
    elif b'<input' in ll:
        hits.append((i+1, 'INPUT_TAG', line.decode('utf-8','replace').strip()))

print(f'\nAll <input> occurrences ({len(hits)} total):')
for ln, tag, content in hits:
    print(f'  L{ln} [{tag}]: {content[:140]}')
