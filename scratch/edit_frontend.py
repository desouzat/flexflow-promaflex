import os

file_path = r"c:\Documentos\BotCase\FlexFlow\frontend\src\pages\KanbanPage.jsx"

if not os.path.exists(file_path):
    print("Error: file does not exist")
    exit(1)

content = open(file_path, "r", encoding="utf-8").read()

target = "const marginVal = parseFloat(selectedPO.margin_percentage);\n                                                                                                         return isNaN(marginVal) ? 'PENDENTE PCP' : (marginVal > 1000 ? '> 1000%' : `${marginVal.toFixed(2)}%`);"

# Let's check if target is in content
if target not in content:
    # Try with different spacing/newlines
    print("Target not found exactly, trying search and replace...")
    
    # We can search for the specific return statement and replace it
    target_part = "return isNaN(marginVal) ? 'PENDENTE PCP' : (marginVal > 1000 ? '> 1000%' : `${marginVal.toFixed(2)}%`);"
    if target_part in content:
        replacement = "return selectedPO.margin_percentage === '***' ? '***' : (isNaN(marginVal) ? 'PENDENTE PCP' : (marginVal > 1000 ? '> 1000%' : `${marginVal.toFixed(2)}%`));"
        content = content.replace(target_part, replacement)
        open(file_path, "w", encoding="utf-8").write(content)
        print("Successfully replaced the return statement!")
    else:
        print("Could not find the target return statement.")
else:
    replacement = "const marginVal = parseFloat(selectedPO.margin_percentage);\n                                                                                                         return selectedPO.margin_percentage === '***' ? '***' : (isNaN(marginVal) ? 'PENDENTE PCP' : (marginVal > 1000 ? '> 1000%' : `${marginVal.toFixed(2)}%`));"
    content = content.replace(target, replacement)
    open(file_path, "w", encoding="utf-8").write(content)
    print("Successfully replaced with exact target!")
