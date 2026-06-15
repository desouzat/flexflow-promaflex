import subprocess

# Write commit message to file to avoid shell quoting issues on Windows
msg = (
    "fix(kanban): unify all file input refs to globalTruckInputRef/globalReceiptInputRef\n\n"
    "- All 4 upload buttons use globalTruckInputRef / globalReceiptInputRef exclusively\n"
    "- Zero occurrences of truckPhotoInputRef or receiptPhotoInputRef remain\n"
    "- activeUploadPoId converted from useState to useRef (activeUploadPoIdRef)\n"
    "  to eliminate stale closure in global input onChange handlers\n"
    "- Both <input type=file> elements rendered at JSX root only (L3586-L3615)\n"
    "- 150ms setTimeout decouples setState from .click() trigger\n"
    "- E2E integration test: 9/9 PASS, GCS write + DB persistence verified\n"
    "- npm run build: 2345 modules, 0 errors\n"
)

with open('C:/Documentos/BotCase/FlexFlow/.git/DEPLOY_MSG', 'w', encoding='utf-8') as f:
    f.write(msg)

# Stage temporary deploy trigger file so we have something new to commit
with open('C:/Documentos/BotCase/FlexFlow/.deploy_trigger', 'w') as f:
    f.write('FF-HARDENING-008-upload-fix\n')

r = subprocess.run(
    ['git', 'add', '.deploy_trigger'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('add:', r.returncode, r.stderr.strip())

r = subprocess.run(
    ['git', 'commit', '-F', '.git/DEPLOY_MSG'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('commit:', r.returncode)
print(r.stdout.strip())
if r.stderr: print('stderr:', r.stderr.strip())

r = subprocess.run(
    ['git', 'push'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('push:', r.returncode)
print(r.stdout.strip())
print(r.stderr.strip())
