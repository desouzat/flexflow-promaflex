import subprocess

msg = (
    "refactor(kanban): extract LogisticsUploadSection as standalone module-scope subcomponent\n\n"
    "FF-HARDENING-008 - architectural rebuild of Expedicao upload UI:\n\n"
    "WHAT CHANGED:\n"
    "- Declared LogisticsUploadSection at MODULE SCOPE (before KanbanPage function)\n"
    "  so it is fully initialized before any render path references it (no TDZ risk)\n"
    "- Component owns its OWN two hidden <input type=file> elements at its root\n"
    "  - truckInputRef + receiptInputRef are local to the subcomponent\n"
    "  - inputs NEVER inside a .map() or conditional block => refs always stable\n"
    "- activePoIdRef (useRef) written synchronously in triggerUpload() before .click()\n"
    "  eliminates stale useState closure bug entirely\n"
    "- e.target.value = '' reset on onChange ENTRY (before file read) enables\n"
    "  same-file re-selection without requiring a ref.current.value reset\n"
    "- All F12 TRACE logs (1,2,3,4,5,ERROR) preserved for UAT\n"
    "- onUploadRequest prop delegates to KanbanPage.handleEvidenceUpload\n\n"
    "DELETED:\n"
    "- Old inline upload JSX block (113 lines) from modal render (L2397-L2509)\n"
    "- Old root-level global inputs (globalTruckInputRef/globalReceiptInputRef) from JSX root\n"
    "- Unused globalTruckInputRef, globalReceiptInputRef, activeUploadPoIdRef declarations\n"
    "  from KanbanPage scope (they now live inside the subcomponent)\n\n"
    "RESULT:\n"
    "- Exactly 2 live <input type=file> elements in entire file (L189, L196)\n"
    "- Both inside LogisticsUploadSection, rendered once at modal content level\n"
    "- Zero legacy/orphaned/duplicate file inputs remain\n"
    "- npm run build: 2345 modules, 0 errors, index-DVs4UIfr.js\n"
)

with open('C:/Documentos/BotCase/FlexFlow/.git/REFACTOR_MSG', 'w', encoding='utf-8') as f:
    f.write(msg)

r = subprocess.run(
    ['git', 'add', 'frontend/src/pages/KanbanPage.jsx'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('add:', r.returncode, r.stderr.strip() or 'OK')

r = subprocess.run(
    ['git', 'commit', '-F', '.git/REFACTOR_MSG'],
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
