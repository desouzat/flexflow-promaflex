import subprocess

msg = (
    "fix(kanban): suppress fetchBoard() during file picker lifetime — root cause of silent TRACE 2\n\n"
    "FF-HARDENING-008 — ROOT CAUSE IDENTIFIED AND FIXED:\n\n"
    "THE KILLER:\n"
    "  window.addEventListener('focus', handleFocus) called fetchBoard() on every\n"
    "  window focus event. The OS file-picker dialog is a separate OS window. When\n"
    "  the user selects a file and the OS dialog closes, Chrome fires a window\n"
    "  'focus' event on the browser page BEFORE dispatching the input's native\n"
    "  'change' event. fetchBoard() called setLoading(true), which triggered the\n"
    "  early-return loading guard (returns a bare loading spinner JSX), causing the\n"
    "  <> fragment containing the file inputs to be UNMOUNTED. The native 'change'\n"
    "  event was then dispatched to a detached DOM element — completely invisible\n"
    "  to both React and native listeners. TRACE 2 was always silent.\n\n"
    "THE FIX:\n"
    "  - isPickerActiveRef = useRef(false) declared at KanbanPage scope\n"
    "  - Set to true synchronously in LogisticsUploadSection.triggerUpload()\n"
    "    before .click() (same event handler tick, preserves User Activation)\n"
    "  - handleFocus checks isPickerActiveRef.current and returns early if true,\n"
    "    skipping the entire fetchBoard() call\n"
    "  - Cleared back to false at the TOP of each native change handler\n"
    "    (handleTruckChange / handleReceiptChange) before file processing\n\n"
    "AUDIT FINDINGS:\n"
    "  - No stopPropagation() or preventDefault() found in upload event chain\n"
    "  - LogisticsUploadSection rendered exactly ONCE (L2623) — confirmed\n"
    "  - Financeiro section (L2700-2760) is read-only display only (no inputs/buttons)\n"
    "  - The 'blinking' fix referenced by Thiago was not a stopPropagation; it was\n"
    "    the async setLogisticsChecklist call inside handleChecklistChange which\n"
    "    caused re-renders. The window focus auto-sync was a separate, unrelated fix\n"
    "    that became the new killer.\n\n"
    "Build: 2345 modules, 0 errors.\n"
)

with open('C:/Documentos/BotCase/FlexFlow/.git/PICKER_GUARD_MSG', 'w', encoding='utf-8') as f:
    f.write(msg)

r = subprocess.run(
    ['git', 'add', 'frontend/src/pages/KanbanPage.jsx'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('add:', r.returncode, r.stderr.strip() or 'OK')

r = subprocess.run(
    ['git', 'commit', '-F', '.git/PICKER_GUARD_MSG'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('commit:', r.returncode, r.stdout.strip())
if r.stderr.strip(): print('WARN:', r.stderr.strip())

r = subprocess.run(
    ['git', 'push'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('push:', r.returncode, r.stdout.strip(), r.stderr.strip())
