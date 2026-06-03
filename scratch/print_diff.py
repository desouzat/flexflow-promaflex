import subprocess
out = subprocess.check_output(['git', 'diff', '--no-color', 'frontend/src/pages/KanbanPage.jsx']).decode('utf-8', 'ignore').splitlines()
for i, line in enumerate(out[100:200]):
    print(f"{i+100}: {line.encode('ascii', 'ignore').decode('ascii')}")
