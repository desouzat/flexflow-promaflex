import re

filepath = r"c:\Documentos\BotCase\FlexFlow\backend\routers\kanban.py"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# Pattern matches 'PurchaseOrder.id == ' followed by alphanumeric, underscore, dot variables.
# Example: PurchaseOrder.id == po_id
pattern = r"PurchaseOrder\.id == ([a-zA-Z0-9_\.]+)"
replacement = r"PurchaseOrder.id == uuid.UUID(str(\1))"

# Check matches
matches = re.findall(pattern, content)
print(f"Found matches to replace: {matches}")

# Perform replacement
new_content = re.sub(pattern, replacement, content)

with open(filepath, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Replacement complete.")
