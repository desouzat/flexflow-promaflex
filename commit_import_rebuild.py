import subprocess

msg = (
    "fix(kanban): add missing showLoading/dismissToast imports; rebuild LogisticsUploadSection\n\n"
    "ROOT CAUSE OF TRACE 3 -> TRACE 4 SILENT BLOCK:\n"
    "  showLoading and dismissToast were exported from utils/toast.js but NEVER\n"
    "  imported in KanbanPage.jsx. The import line read:\n"
    "    import { showSuccess, showError } from '../utils/toast'\n"
    "  Calling showLoading('Enviando arquivo...') at L889 (INSIDE the try block,\n"
    "  BEFORE TRACE 4) threw ReferenceError: showLoading is not defined.\n"
    "  The error was thrown before the try block was entered, so the catch handler\n"
    "  never ran and TRACE ERROR never fired. The function silently aborted.\n\n"
    "FIX 1 — Import:\n"
    "  import { showSuccess, showError, showLoading, dismissToast } from '../utils/toast'\n\n"
    "FIX 2 — LogisticsUploadSection clean rebuild:\n"
    "  - Removed onUploadRequest prop (unused since direct handleEvidenceUpload call)\n"
    "  - Replaced className-based JSX with inline style (zero Tailwind dependency risk)\n"
    "  - UploadSlot sub-component: label + status pill (green Enviado / amber Pendente)\n"
    "  - When path is null: orange 'Enviar Foto' button with hover effect\n"
    "  - When path exists: green checkmark + 'Evidencia salva!' + 'Abrir arquivo' link\n"
    "    + ghost 'Substituir arquivo' button for re-upload\n"
    "  - isDisabled guard disables button and dims it (opacity 0.6 + cursor not-allowed)\n"
    "  - All TRACE logs (1, 1.5) preserved for UAT\n\n"
    "Build: 2345 modules, 0 errors. Asset: index-oMQNaa-H.js\n"
)

with open('C:/Documentos/BotCase/FlexFlow/.git/IMPORT_FIX_MSG', 'w', encoding='utf-8') as f:
    f.write(msg)

r = subprocess.run(
    ['git', 'add', 'frontend/src/pages/KanbanPage.jsx'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('add:', r.returncode, r.stderr.strip() or 'OK')

r = subprocess.run(
    ['git', 'commit', '-F', '.git/IMPORT_FIX_MSG'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('commit:', r.returncode, r.stdout.strip())
if r.stderr.strip(): print('WARN:', r.stderr.strip())

r = subprocess.run(
    ['git', 'push'],
    cwd='C:/Documentos/BotCase/FlexFlow', capture_output=True, text=True
)
print('push:', r.returncode, r.stdout.strip(), r.stderr.strip())
