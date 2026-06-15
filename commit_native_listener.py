import subprocess

msg = (
    "fix(kanban): bypass React synthetic onChange with native addEventListener for file inputs\n\n"
    "FF-HARDENING-008 - DIAGNOSIS:\n"
    "The JSX onChange on <input type=file> is part of React's synthetic event system.\n"
    "When KanbanPage re-renders between the moment .click() opens the OS file picker\n"
    "and the moment the user selects a file, React can re-attach its internal synthetic\n"
    "event listener to a new fiber, orphaning the native picker's dispatch channel.\n"
    "Result: file picker opens, user selects file, native 'change' event fires on the\n"
    "original DOM element, but React's new synthetic listener misses it. TRACE 2 = silent.\n\n"
    "FIX:\n"
    "- Added useEffect (empty deps = runs once on mount) that attaches native\n"
    "  element.addEventListener('change', handler) directly to both input DOM elements.\n"
    "- Native listeners are immune to React re-render cycles because they are registered\n"
    "  on the actual DOM node, not on React's virtual fiber.\n"
    "- Removed JSX onChange props from the inputs (they were the unreliable path).\n"
    "- Added handleUploadRef = useRef(null) to hold a current-always reference to\n"
    "  handleEvidenceUpload, so the frozen closure inside the native listener always\n"
    "  calls the latest version of the function.\n"
    "- handleUploadRef.current = handleEvidenceUpload is set on every render (inside the\n"
    "  function body itself) ensuring the ref is always up-to-date.\n\n"
    "FLOW (now reliable):\n"
    "  1. Button onClick -> triggerUpload() -> TRACE 1 + TRACE 1.5 -> .click() -> OS picker\n"
    "  2. User selects file -> native 'change' event fires on DOM element\n"
    "  3. Native listener reads file + poId -> TRACE 2 -> handleEvidenceUpload\n"
    "  4. TRACE 3 -> Axios POST -> TRACE 5 -> persistence confirmed\n\n"
    "Build: 2345 modules, 0 errors.\n"
)

with open('C:/Documentos/BotCase/FlexFlow/.git/NATIVE_LISTENER_MSG', 'w', encoding='utf-8') as f:
    f.write(msg)

r = subprocess.run(
    ['git', 'add', 'frontend/src/pages/KanbanPage.jsx'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('add:', r.returncode, r.stderr.strip() or 'OK')

r = subprocess.run(
    ['git', 'commit', '-F', '.git/NATIVE_LISTENER_MSG'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('commit:', r.returncode, r.stdout.strip())
if r.stderr.strip(): print('WARN:', r.stderr.strip())

r = subprocess.run(
    ['git', 'push'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('push:', r.returncode, r.stdout.strip(), r.stderr.strip())
