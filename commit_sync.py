import subprocess

msg = (
    "fix(kanban): remove setTimeout from LogisticsUploadSection.triggerUpload - call .click() synchronously\n\n"
    "Root cause: Chrome's User Activation security policy (https://html.spec.whatwg.org/multipage/interaction.html#activation)\n"
    "strictly requires that programmatic .click() on <input type=file> is called SYNCHRONOUSLY\n"
    "within the same event handler that received the user gesture (button click).\n\n"
    "Even a setTimeout(..., 0) or setTimeout(..., 150) breaks the activation chain because\n"
    "the browser considers the task queue boundary as a new execution context.\n"
    "The result: .click() fires silently with no file picker dialog opening.\n\n"
    "FIX:\n"
    "- Removed both setTimeout wrappers from triggerUpload()\n"
    "- activePoIdRef.current = poId is set synchronously (useRef, no re-render)\n"
    "- truckInputRef.current?.click() / receiptInputRef.current?.click() called immediately\n"
    "- The file picker now opens within the same microtask as the user's button press\n\n"
    "No other logic changed. Build: 2345 modules, 0 errors.\n"
)

with open('C:/Documentos/BotCase/FlexFlow/.git/SYNC_MSG', 'w', encoding='utf-8') as f:
    f.write(msg)

r = subprocess.run(
    ['git', 'add', 'frontend/src/pages/KanbanPage.jsx'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('add:', r.returncode, r.stderr.strip() or 'OK')

r = subprocess.run(
    ['git', 'commit', '-F', '.git/SYNC_MSG'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('commit:', r.returncode, r.stdout.strip())
if r.stderr.strip(): print('stderr:', r.stderr.strip())
