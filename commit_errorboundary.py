import subprocess

msg = (
    "fix(kanban): move file inputs outside ErrorBoundary to guarantee DOM mounting\n\n"
    "FF-HARDENING-008 - Root cause: inputs inside LogisticsUploadSection were inside\n"
    "<ErrorBoundary>, meaning they could be unmounted/replaced if ErrorBoundary caught\n"
    "an error. More critically, inputs inside a subcomponent rendered conditionally in\n"
    "the modal could be unmounted before refs resolve.\n\n"
    "ARCHITECTURE CHANGE:\n"
    "- globalTruckInputRef, globalReceiptInputRef, activeUploadPoIdRef declared at\n"
    "  KanbanPage scope (useRef)\n"
    "- Two <input type=file> rendered at KanbanPage return root, BEFORE <ErrorBoundary>\n"
    "  wrapped in <> fragment so they are ALWAYS mounted unconditionally\n"
    "- LogisticsUploadSection now receives truckInputRef, receiptInputRef, activePoIdRef\n"
    "  as props (does NOT own its own inputs)\n"
    "- triggerUpload() calls ref.current?.click() synchronously (no setTimeout)\n"
    "- onChange: reads file BEFORE resetting e.target.value (fixes FileList-clear bug)\n\n"
    "DIAGNOSTICS ADDED:\n"
    "- [F12 TRACE 1.5] logs ref.current status immediately before .click() so UAT can\n"
    "  confirm the DOM element is attached\n\n"
    "RESULT:\n"
    "- Inputs are ALWAYS mounted - independent of ErrorBoundary, modal, or conditional state\n"
    "- refs guaranteed non-null at click time\n"
    "- npm run build: 2345 modules, 0 errors\n"
)

with open('C:/Documentos/BotCase/FlexFlow/.git/ERRORBOUNDARY_MSG', 'w', encoding='utf-8') as f:
    f.write(msg)

r = subprocess.run(
    ['git', 'add', 'frontend/src/pages/KanbanPage.jsx'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('add:', r.returncode, r.stderr.strip() or 'OK')

r = subprocess.run(
    ['git', 'commit', '-F', '.git/ERRORBOUNDARY_MSG'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('commit:', r.returncode, r.stdout.strip())
if r.stderr.strip(): print('WARN:', r.stderr.strip())

r = subprocess.run(
    ['git', 'push'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('push:', r.returncode, r.stdout.strip(), r.stderr.strip())
