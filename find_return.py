FILE = 'C:/Documentos/BotCase/FlexFlow/frontend/src/pages/KanbanPage.jsx'
with open(FILE, 'rb') as f:
    lines = f.read().split(b'\n')

for i, l in enumerate(lines):
    dec = l.decode('utf-8', 'replace').rstrip()
    if b'return (' in l and i > 200:
        print(f'KanbanPage return( -> L{i+1}: {dec}')
        break

for i, l in enumerate(lines):
    if b'<ErrorBoundary' in l:
        dec = l.decode('utf-8', 'replace').strip()
        print(f'ErrorBoundary L{i+1}: {dec}')
