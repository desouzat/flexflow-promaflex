import subprocess

msg = (
    "fix(kanban): replace useEffect listener binding with Callback Ref pattern\n\n"
    "FF-HARDENING-008 — DIAGNOSIS:\n"
    "useEffect([], []) fires synchronously after the FIRST completed render of\n"
    "KanbanPage. The first render is when loading=true, which triggers the early-return\n"
    "guard: `if (loading) return <LoadingSpinner />`. The main `return (<>...)` block\n"
    "that contains the file inputs is NOT reached during this render. The inputs do not\n"
    "exist in the DOM yet. globalTruckInputRef.current and globalReceiptInputRef.current\n"
    "are both null. The useEffect captures null references, attaches listeners to null,\n"
    "and exits. Zero listeners are ever bound. TRACE 2 is always silent.\n\n"
    "THE FIX — Callback Ref pattern:\n"
    "  ref={(node) => { ... }}\n"
    "React calls this function synchronously with the DOM node at the exact moment the\n"
    "element mounts (node = HTMLElement) and with null when it unmounts (node = null).\n"
    "There is no async delay. The onchange handler is attached via the DOM property\n"
    "(node.onchange = handler) which replaces atomically \u2014 no bookkeeping needed.\n\n"
    "IMPLEMENTATION:\n"
    "  - Removed useEffect listener block entirely\n"
    "  - Both <input type=file> elements use callback ref functions\n"
    "  - Inside callback: globalTruckInputRef.current = node (keeps .click() working)\n"
    "  - Inside callback: node.onchange = handler (wired synchronously at mount)\n"
    "  - isPickerActiveRef, activeUploadPoIdRef, handleUploadRef all preserved\n"
    "  - isPickerActiveRef.current set to false at onchange entry (window focus guard)\n"
    "  - handleUploadRef.current = handleEvidenceUpload updated inside function body\n\n"
    "PREVIOUS LAYERS PRESERVED:\n"
    "  - isPickerActiveRef guard in handleFocus (suppresses fetchBoard during picker)\n"
    "  - globalTruckInputRef / globalReceiptInputRef still useRef, passed as props\n"
    "  - LogisticsUploadSection.triggerUpload sets isPickerActiveRef.current = true\n"
    "  - Inputs rendered before <ErrorBoundary> in <> fragment (always in DOM)\n\n"
    "Build: 2345 modules, 0 errors.\n"
)

with open('C:/Documentos/BotCase/FlexFlow/.git/CALLBACK_REF_MSG', 'w', encoding='utf-8') as f:
    f.write(msg)

r = subprocess.run(
    ['git', 'add', 'frontend/src/pages/KanbanPage.jsx'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('add:', r.returncode, r.stderr.strip() or 'OK')

r = subprocess.run(
    ['git', 'commit', '-F', '.git/CALLBACK_REF_MSG'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('commit:', r.returncode, r.stdout.strip())
if r.stderr.strip(): print('WARN:', r.stderr.strip())

r = subprocess.run(
    ['git', 'push'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('push:', r.returncode, r.stdout.strip(), r.stderr.strip())
