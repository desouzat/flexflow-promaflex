import os

brain_dir = r"C:\Users\Thiago\.gemini\antigravity\brain"
found_urls = set()

for root, dirs, files in os.walk(brain_dir):
    for file in files:
        if file.endswith((".jsonl", ".log", ".txt", ".json", ".md")):
            path = os.path.join(root, file)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        if "run.app" in line:
                            # Extract words that contain run.app
                            for word in line.split():
                                if "run.app" in word:
                                    # clean up trailing characters like ", ', ], }, etc.
                                    clean_word = word.strip('"\'[]{},;()')
                                    if clean_word.startswith("http"):
                                        found_urls.add(clean_word)
            except Exception:
                pass

print("Found URLs:")
for url in found_urls:
    print(url)
