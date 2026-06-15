import subprocess

r = subprocess.run(
    ['git', 'add', 'frontend/src/pages/KanbanPage.jsx'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('add:', r.returncode, r.stderr.strip() or 'OK')

msg = (
    "fix(kanban): remove handleUploadRef — call handleEvidenceUpload directly\n\n"
    "The handleUploadRef = useRef(null) was only ever set INSIDE handleEvidenceUpload\n"
    "itself (chicken-and-egg pattern). On first upload attempt, handleUploadRef.current\n"
    "was null, so the guard 'if (file && poId && handleUploadRef.current)' silently\n"
    "short-circuited and handleEvidenceUpload was never invoked.\n\n"
    "Fix: both node.onchange callbacks in the KanbanPage callback-ref inputs now call\n"
    "handleEvidenceUpload() directly. It is declared in KanbanPage scope and fully\n"
    "accessible via closure from the JSX return block.\n\n"
    "Changes:\n"
    "  - Removed: const handleUploadRef = useRef(null)\n"
    "  - Removed: handleUploadRef.current = handleEvidenceUpload (inside the function)\n"
    "  - Changed: if (file && poId && handleUploadRef.current) { handleUploadRef.current(...) }\n"
    "  - To:      if (file && poId) { handleEvidenceUpload(...) }\n"
    "  - Applied to both truck (foto_carga_path) and receipt (foto_canhoto_path) inputs\n\n"
    "Build: 2345 modules, 0 errors. Asset: index-BwxZiHlX.js\n"
)

r = subprocess.run(
    ['git', 'commit', '-m', msg],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('commit:', r.returncode, r.stdout.strip())
if r.stderr.strip(): print('WARN:', r.stderr.strip())

r = subprocess.run(
    ['git', 'push'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('push:', r.returncode, r.stdout.strip(), r.stderr.strip())
