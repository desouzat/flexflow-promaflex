import os

filepath = r"c:\Documentos\BotCase\FlexFlow\frontend\src\pages\KanbanPage.jsx"
with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Let's verify each target area before modifying.
# 1. Cargo Photo Reupload (lines 2182 to 2185, which are index 2181 to 2184)
# Let's print what's currently there.
print("Target 1 (Cargo Reupload):")
for i in range(2181, 2185):
    print(f"{i+1}: {repr(lines[i])}")

# Let's replace lines 2181 to 2184 (inclusive)
# 2182 to 2185 in 1-based:
new_cargo_reupload_lines = [
    '                                                                        {!isPhaseADisabled && (\n',
    '                                                                         <div className="pt-1">\n',
    '                                                                             <input\n',
    '                                                                                 type="file"\n',
    '                                                                                 accept=".pdf,.jpg,.jpeg,.png"\n',
    '                                                                                 onChange={(e) => handleEvidenceUpload(\'foto_carga_path\', e.target.files[0])}\n',
    '                                                                                 className="w-full text-sm text-gray-550 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-orange-50 file:text-orange-700 hover:file:bg-orange-100 cursor-pointer border border-gray-300 rounded-lg p-1"\n',
    '                                                                             />\n',
    '                                                                         </div>\n',
    '                                                                     )}\n'
]

# 2. Cargo Photo Upload (lines 2188 to 2209, which are index 2187 to 2208)
print("\nTarget 2 (Cargo Upload):")
for i in range(2187, 2209):
    print(f"{i+1}: {repr(lines[i])}")

new_cargo_upload_lines = [
    '                                                                 <div>\n',
    '                                                                     <input\n',
    '                                                                         type="file"\n',
    '                                                                         accept=".pdf,.jpg,.jpeg,.png"\n',
    '                                                                         onChange={(e) => handleEvidenceUpload(\'foto_carga_path\', e.target.files[0])}\n',
    '                                                                         disabled={isPhaseADisabled}\n',
    '                                                                         className="w-full text-sm text-gray-550 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-orange-50 file:text-orange-700 hover:file:bg-orange-100 cursor-pointer border border-gray-300 rounded-lg p-1"\n',
    '                                                                     />\n',
    '                                                                 </div>\n'
]

# 3. Canhoto Photo Reupload (lines 2232 to 2254, which are index 2231 to 2253)
print("\nTarget 3 (Canhoto Reupload):")
for i in range(2231, 2254):
    print(f"{i+1}: {repr(lines[i])}")

new_canhoto_reupload_lines = [
    '                                                                      {!isPhaseADisabled && (\n',
    '                                                                          <div className="pt-1">\n',
    '                                                                              <input\n',
    '                                                                                  type="file"\n',
    '                                                                                  accept=".pdf,.jpg,.jpeg,.png"\n',
    '                                                                                  onChange={(e) => handleEvidenceUpload(\'foto_canhoto_path\', e.target.files[0])}\n',
    '                                                                                  className="w-full text-sm text-gray-550 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-orange-50 file:text-orange-700 hover:file:bg-orange-100 cursor-pointer border border-gray-300 rounded-lg p-1"\n',
    '                                                                              />\n',
    '                                                                          </div>\n',
    '                                                                      )}\n'
]

# 4. Canhoto Photo Upload (lines 2257 to 2278, which are index 2256 to 2277)
print("\nTarget 4 (Canhoto Upload):")
for i in range(2256, 2278):
    print(f"{i+1}: {repr(lines[i])}")

new_canhoto_upload_lines = [
    '                                                                  <div>\n',
    '                                                                      <input\n',
    '                                                                          type="file"\n',
    '                                                                          accept=".pdf,.jpg,.jpeg,.png"\n',
    '                                                                          onChange={(e) => handleEvidenceUpload(\'foto_canhoto_path\', e.target.files[0])}\n',
    '                                                                          disabled={isPhaseADisabled}\n',
    '                                                                          className="w-full text-sm text-gray-550 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-orange-50 file:text-orange-700 hover:file:bg-orange-100 cursor-pointer border border-gray-300 rounded-lg p-1"\n',
    '                                                                      />\n',
    '                                                                  </div>\n'
]

# Assemble the new lines
# Because replacing ranges changes indices, we should replace from bottom to top!
# Order of replacement: Target 4 (2256-2277), Target 3 (2231-2253), Target 2 (2187-2208), Target 1 (2181-2184).
lines[2256:2278] = new_canhoto_upload_lines
lines[2231:2254] = new_canhoto_reupload_lines
lines[2187:2209] = new_cargo_upload_lines
lines[2181:2185] = new_cargo_reupload_lines

# Write back
with open(filepath, "w", encoding="utf-8") as f:
    f.writelines(lines)

print("Replacement complete!")
