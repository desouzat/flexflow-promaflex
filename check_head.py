import subprocess

r = subprocess.run(
    ['git', 'show', 'HEAD:frontend/src/pages/KanbanPage.jsx'],
    cwd='C:/Documentos/BotCase/FlexFlow',
    capture_output=True, text=True, errors='replace'
)
lines = r.stdout.splitlines()
print(f'HEAD file has {len(lines)} lines')

patterns = ['activeUploadPoIdRef', 'setActiveUploadPoId', 'globalTruckInputRef', 'TRACE 2', 'type=.file.']
import re
for p in patterns:
    hits = [(i+1, l.strip()) for i, l in enumerate(lines) if re.search(p, l)]
    print(f'\n[{p}] -> {len(hits)} hit(s):')
    for ln, content in hits[:4]:
        print(f'  L{ln}: {content[:110]}')
