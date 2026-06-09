import os
import json

app_data_dir = r"C:\Users\Thiago\AppData\Roaming" # Wait, App Data Directory: C:\Users\Thiago\.gemini\antigravity
brain_dir = r"C:\Users\Thiago\.gemini\antigravity\brain"

# Find all transcript.jsonl files
for root, dirs, files in os.walk(brain_dir):
    for file in files:
        if file == "transcript.jsonl":
            path = os.path.join(root, file)
            print(f"Checking {path}...")
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "run.app" in line:
                        print(f"FOUND in {path}:")
                        print(line[:500])
