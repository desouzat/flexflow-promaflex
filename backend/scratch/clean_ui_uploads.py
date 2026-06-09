filepath = r"c:\Documentos\BotCase\FlexFlow\frontend\src\pages\KanbanPage.jsx"

with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Let's print the target lines to verify before slice replacement
print("--- TARGET 1: Cargo Reupload (lines 2182-2191) ---")
for i in range(2181, 2191):
    print(f"{i+1}: {repr(lines[i])}")

new_cargo_reupload_lines = [
    '                                                                        {!isPhaseADisabled && (\n',
    '                                                                         <div className="pt-1">\n',
    '                                                                             <input\n',
    '                                                                                 type="file"\n',
    '                                                                                 accept=".pdf,.jpg,.jpeg,.png"\n',
    '                                                                                 onClick={(e) => { e.stopPropagation(); e.target.value = null; }}\n',
    '                                                                                 onChange={(e) => handleEvidenceUpload(\'foto_carga_path\', e.target.files[0])}\n',
    '                                                                                 className="hidden"\n',
    '                                                                                 id="foto-carga-reupload"\n',
    '                                                                             />\n',
    '                                                                             <button\n',
    '                                                                                 type="button"\n',
    '                                                                                 onClick={(e) => {\n',
    '                                                                                     e.stopPropagation();\n',
    '                                                                                     document.getElementById(\'foto-carga-reupload\').click();\n',
    '                                                                                 }}\n',
    '                                                                                 className="inline-flex items-center gap-1 text-[10px] text-gray-550 bg-gray-100 hover:bg-gray-200 border border-gray-305 rounded px-2 py-0.5 cursor-pointer transition-colors"\n',
    '                                                                             >\n',
    '                                                                                 Substituir Arquivo\n',
    '                                                                             </button>\n',
    '                                                                         </div>\n',
    '                                                                     )}\n'
]

print("--- TARGET 2: Cargo Upload (lines 2194-2202) ---")
for i in range(2193, 2202):
    print(f"{i+1}: {repr(lines[i])}")

new_cargo_upload_lines = [
    '                                                                  <div>\n',
    '                                                                      <input\n',
    '                                                                          type="file"\n',
    '                                                                          accept=".pdf,.jpg,.jpeg,.png"\n',
    '                                                                          onClick={(e) => { e.stopPropagation(); e.target.value = null; }}\n',
    '                                                                          onChange={(e) => handleEvidenceUpload(\'foto_carga_path\', e.target.files[0])}\n',
    '                                                                          className="hidden"\n',
    '                                                                          id="foto-carga-upload"\n',
    '                                                                          disabled={isPhaseADisabled}\n',
    '                                                                      />\n',
    '                                                                      <button\n',
    '                                                                          type="button"\n',
    '                                                                          onClick={(e) => {\n',
    '                                                                              e.stopPropagation();\n',
    '                                                                              document.getElementById(\'foto-carga-upload\').click();\n',
    '                                                                          }}\n',
    '                                                                          disabled={isPhaseADisabled}\n',
    '                                                                          className={`flex items-center justify-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-lg transition-colors text-xs font-semibold shadow-xs ${isPhaseADisabled ? \'cursor-not-allowed opacity-50 bg-orange-400\' : \'hover:bg-orange-700 cursor-pointer\'}`}\n',
    '                                                                      >\n',
    '                                                                          Enviar Foto\n',
    '                                                                      </button>\n',
    '                                                                  </div>\n'
]

print("--- TARGET 3: Canhoto Reupload (lines 2225-2234) ---")
for i in range(2224, 2234):
    print(f"{i+1}: {repr(lines[i])}")

new_canhoto_reupload_lines = [
    '                                                                       {!isPhaseADisabled && (\n',
    '                                                                           <div className="pt-1">\n',
    '                                                                               <input\n',
    '                                                                                   type="file"\n',
    '                                                                                   accept=".pdf,.jpg,.jpeg,.png"\n',
    '                                                                                   onClick={(e) => { e.stopPropagation(); e.target.value = null; }}\n',
    '                                                                                   onChange={(e) => handleEvidenceUpload(\'foto_canhoto_path\', e.target.files[0])}\n',
    '                                                                                   className="hidden"\n',
    '                                                                                   id="foto-canhoto-reupload"\n',
    '                                                                               />\n',
    '                                                                               <button\n',
    '                                                                                   type="button"\n',
    '                                                                                   onClick={(e) => {\n',
    '                                                                                       e.stopPropagation();\n',
    '                                                                                       document.getElementById(\'foto-canhoto-reupload\').click();\n',
    '                                                                                   }}\n',
    '                                                                                   className="inline-flex items-center gap-1 text-[10px] text-gray-550 bg-gray-100 hover:bg-gray-200 border border-gray-305 rounded px-2 py-0.5 cursor-pointer transition-colors"\n',
    '                                                                               >\n',
    '                                                                                   Substituir Arquivo\n',
    '                                                                               </button>\n',
    '                                                                           </div>\n',
    '                                                                       )}\n'
]

print("--- TARGET 4: Canhoto Upload (lines 2237-2245) ---")
for i in range(2236, 2245):
    print(f"{i+1}: {repr(lines[i])}")

new_canhoto_upload_lines = [
    '                                                                   <div>\n',
    '                                                                       <input\n',
    '                                                                           type="file"\n',
    '                                                                           accept=".pdf,.jpg,.jpeg,.png"\n',
    '                                                                           onClick={(e) => { e.stopPropagation(); e.target.value = null; }}\n',
    '                                                                           onChange={(e) => handleEvidenceUpload(\'foto_canhoto_path\', e.target.files[0])}\n',
    '                                                                           className="hidden"\n',
    '                                                                           id="foto-canhoto-upload"\n',
    '                                                                           disabled={isPhaseADisabled}\n',
    '                                                                       />\n',
    '                                                                       <button\n',
    '                                                                           type="button"\n',
    '                                                                           onClick={(e) => {\n',
    '                                                                               e.stopPropagation();\n',
    '                                                                               document.getElementById(\'foto-canhoto-upload\').click();\n',
    '                                                                           }}\n',
    '                                                                           disabled={isPhaseADisabled}\n',
    '                                                                           className={`flex items-center justify-center gap-2 px-4 py-2 bg-orange-600 text-white rounded-lg transition-colors text-xs font-semibold shadow-xs ${isPhaseADisabled ? \'cursor-not-allowed opacity-50 bg-orange-400\' : \'hover:bg-orange-700 cursor-pointer\'}`}\n',
    '                                                                       >\n',
    '                                                                           Enviar Foto\n',
    '                                                                       </button>\n',
    '                                                                   </div>\n'
]

# Perform slice-based replacement from bottom to top to preserve indices
lines[2236:2245] = new_canhoto_upload_lines
lines[2224:2234] = new_canhoto_reupload_lines
lines[2193:2202] = new_cargo_upload_lines
lines[2181:2191] = new_cargo_reupload_lines

# Write back
with open(filepath, "w", encoding="utf-8") as f:
    f.writelines(lines)

print("Replacement successfully completed!")
