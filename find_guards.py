FILE = 'C:/Documentos/BotCase/FlexFlow/frontend/src/pages/KanbanPage.jsx'
with open(FILE, 'rb') as f:
    lines = f.read().split(b'\n')

# Find early return guards between KanbanPage function and main return
for i, l in enumerate(lines):
    if i < 186 or i > 1380:
        continue
    dec = l.decode('utf-8', 'replace').strip()
    triggers = ('if (loading', 'if (error', 'if (!boardData', 'return null', 'return <div')
    if any(dec.startswith(t) for t in triggers):
        raw = l.decode('utf-8', 'replace').rstrip()
        print(f'L{i+1}: {raw}')
        nxt = lines[i+1].decode('utf-8', 'replace').rstrip() if i+1 < len(lines) else ''
        print(f'L{i+2}: {nxt}')
        print('---')
