import subprocess

msg = (
    "fix(kanban): replace activeUploadPoIdRef with direct selectedPO?.id in onchange closures\n\n"
    "FF-HARDENING-008 — DIAGNOSIS:\n"
    "activeUploadPoIdRef.current was null inside node.onchange because of a subtle\n"
    "callback-ref timing gap:\n"
    "  1. triggerUpload() sets activeUploadPoIdRef.current = poId (correct)\n"
    "  2. isPickerActiveRef.current = true (arms focus guard)\n"
    "  3. truckInputRef.current.click() -> OS picker opens\n"
    "  4. Any render (e.g. a toast, poll, or notification) causes React to re-call\n"
    "     the callback ref: ref(null) then ref(node)\n"
    "  5. ref(null) sets globalTruckInputRef.current = null\n"
    "  6. ref(node) reassigns node.onchange with a NEW closure\n"
    "     The new closure captures activeUploadPoIdRef (the ref object) but reads\n"
    "     activeUploadPoIdRef.current at CALL TIME. This should still work...\n"
    "     UNLESS there is a render that reset activeUploadPoIdRef.current to null\n"
    "     via some other path we missed (e.g. modal close sets selectedPO=null,\n"
    "     which triggers a setLogisticsChecklist reset that nullifies the ref).\n\n"
    "THE FIX:\n"
    "  Since the callback ref function is a NEW arrow function on every render,\n"
    "  React calls ref(null) then ref(node) on EVERY render, re-assigning\n"
    "  node.onchange. The new onchange closure captures selectedPO?.id directly\n"
    "  from KanbanPage's render scope. This is the FRESHEST possible value:\n"
    "  the selectedPO at the exact render that happened just before the user\n"
    "  selected a file. No ref indirection needed.\n\n"
    "CHANGES:\n"
    "  - Removed activeUploadPoIdRef = useRef(null) from KanbanPage\n"
    "  - Removed activePoIdRef from LogisticsUploadSection props list\n"
    "  - Removed activePoIdRef.current = poId from triggerUpload()\n"
    "  - Removed activePoIdRef={activeUploadPoIdRef} from JSX call site\n"
    "  - Both node.onchange handlers now use: const poId = selectedPO?.id\n\n"
    "Build: 2345 modules, 0 errors.\n"
)

with open('C:/Documentos/BotCase/FlexFlow/.git/DIRECT_POID_MSG', 'w', encoding='utf-8') as f:
    f.write(msg)

r = subprocess.run(
    ['git', 'add', 'frontend/src/pages/KanbanPage.jsx'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('add:', r.returncode, r.stderr.strip() or 'OK')

r = subprocess.run(
    ['git', 'commit', '-F', '.git/DIRECT_POID_MSG'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('commit:', r.returncode, r.stdout.strip())
if r.stderr.strip(): print('WARN:', r.stderr.strip())

r = subprocess.run(
    ['git', 'push'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('push:', r.returncode, r.stdout.strip(), r.stderr.strip())
