import os

filepath = r"c:\Documentos\BotCase\FlexFlow\frontend\src\pages\KanbanPage.jsx"
with open(filepath, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Cargo Photo Reupload Section
old_cargo_reupload = """                                                                       {!isPhaseADisabled && (
                                                                             </button>
                                                                         </div>
                                                                     )}"""

new_cargo_reupload = """                                                                       {!isPhaseADisabled && (
                                                                         <div className="pt-1">
                                                                             <input
                                                                                 type="file"
                                                                                 accept=".pdf,.jpg,.jpeg,.png"
                                                                                 onChange={(e) => handleEvidenceUpload('foto_carga_path', e.target.files[0])}
                                                                                 className="w-full text-sm text-gray-550 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-orange-50 file:text-orange-700 hover:file:bg-orange-100 cursor-pointer border border-gray-300 rounded-lg p-1"
                                                                             />
                                                                         </div>
                                                                     )}"""

# 2. Cargo Photo Upload Section
old_cargo_upload = """                                                                 <div>
                                                                     <input
                                                                         type="file"
                                                                         accept="image/*"
                                                                         onClick={(e) => { e.stopPropagation(); e.target.value = null; }}
                                                                         onChange={(e) => handleEvidenceUpload('foto_carga_path', e.target.files[0])}
                                                                         className="hidden"
                                                                         id="foto-carga-upload"
                                                                         disabled={uploadingEvidence || isPhaseADisabled}
                                                                     />
                                                                     <button
                                                                         type="button"
                                                                         onClick={(e) => {
                                                                             e.stopPropagation();
                                                                             document.getElementById('foto-carga-upload').click();
                                                                         }}
                                                                         className={`flex items-center justify-center gap-2 px-4 py-2 bg-cyan-600 text-white rounded-lg transition-colors text-xs font-semibold shadow-xs ${isPhaseADisabled ? 'cursor-not-allowed opacity-50 bg-cyan-400' : 'hover:bg-cyan-700 cursor-pointer'}`}
                                                                     >
                                                                         <Upload className="w-4 h-4" />
                                                                         {uploadingEvidence ? 'Enviando...' : 'Enviar Foto da Carga'}
                                                                     </button>
                                                                 </div>"""

new_cargo_upload = """                                                                 <div>
                                                                     <input
                                                                         type="file"
                                                                         accept=".pdf,.jpg,.jpeg,.png"
                                                                         onChange={(e) => handleEvidenceUpload('foto_carga_path', e.target.files[0])}
                                                                         disabled={isPhaseADisabled}
                                                                         className="w-full text-sm text-gray-550 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-orange-50 file:text-orange-700 hover:file:bg-orange-100 cursor-pointer border border-gray-300 rounded-lg p-1"
                                                                     />
                                                                 </div>"""

# 3. Canhoto Photo Reupload Section
old_canhoto_reupload = """                                                                      {!isPhaseADisabled && (
                                                                          <div className="pt-1">
                                                                              <input
                                                                                  type="file"
                                                                                  accept="image/*"
                                                                                  onClick={(e) => { e.stopPropagation(); e.target.value = null; }}
                                                                                  onChange={(e) => handleEvidenceUpload('foto_canhoto_path', e.target.files[0])}
                                                                                  className="hidden"
                                                                                  id="foto-canhoto-reupload"
                                                                                  disabled={uploadingEvidence}
                                                                              />
                                                                              <button
                                                                                  type="button"
                                                                                  onClick={(e) => {
                                                                                      e.stopPropagation();
                                                                                      document.getElementById('foto-canhoto-reupload').click();
                                                                                  }}
                                                                                  className="inline-flex items-center gap-1 text-[10px] text-gray-555 bg-gray-100 hover:bg-gray-200 border border-gray-305 rounded px-2 py-0.5 cursor-pointer transition-colors"
                                                                              >
                                                                                  Substituir Arquivo
                                                                              </button>
                                                                          </div>
                                                                      )}"""

# Let's also check for text-gray-500 in old_canhoto_reupload
old_canhoto_reupload_v2 = """                                                                      {!isPhaseADisabled && (
                                                                          <div className="pt-1">
                                                                              <input
                                                                                  type="file"
                                                                                  accept="image/*"
                                                                                  onClick={(e) => { e.stopPropagation(); e.target.value = null; }}
                                                                                  onChange={(e) => handleEvidenceUpload('foto_canhoto_path', e.target.files[0])}
                                                                                  className="hidden"
                                                                                  id="foto-canhoto-reupload"
                                                                                  disabled={uploadingEvidence}
                                                                              />
                                                                              <button
                                                                                  type="button"
                                                                                  onClick={(e) => {
                                                                                      e.stopPropagation();
                                                                                      document.getElementById('foto-canhoto-reupload').click();
                                                                                  }}
                                                                                  className="inline-flex items-center gap-1 text-[10px] text-gray-500 bg-gray-100 hover:bg-gray-200 border border-gray-305 rounded px-2 py-0.5 cursor-pointer transition-colors"
                                                                              >
                                                                                  Substituir Arquivo
                                                                              </button>
                                                                          </div>
                                                                      )}"""

new_canhoto_reupload = """                                                                      {!isPhaseADisabled && (
                                                                          <div className="pt-1">
                                                                              <input
                                                                                  type="file"
                                                                                  accept=".pdf,.jpg,.jpeg,.png"
                                                                                  onChange={(e) => handleEvidenceUpload('foto_canhoto_path', e.target.files[0])}
                                                                                  className="w-full text-sm text-gray-550 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-orange-50 file:text-orange-700 hover:file:bg-orange-100 cursor-pointer border border-gray-300 rounded-lg p-1"
                                                                              />
                                                                          </div>
                                                                      )}"""

# 4. Canhoto Photo Upload Section
old_canhoto_upload = """                                                                  Anexo (opcional, PDF/JPG/PNG, máx 5MB)
                                                                Anexo (opcional, PDF/JPG/PNG, máx 5MB)"""  # Wait, let's use the exact string below

old_canhoto_upload = """                                                                  <div>
                                                                      <input
                                                                          type="file"
                                                                          accept="image/*"
                                                                          onClick={(e) => { e.stopPropagation(); e.target.value = null; }}
                                                                          onChange={(e) => handleEvidenceUpload('foto_canhoto_path', e.target.files[0])}
                                                                          className="hidden"
                                                                          id="foto-canhoto-upload"
                                                                          disabled={uploadingEvidence || isPhaseADisabled}
                                                                      />
                                                                      <button
                                                                          type="button"
                                                                          onClick={(e) => {
                                                                              e.stopPropagation();
                                                                              document.getElementById('foto-canhoto-upload').click();
                                                                          }}
                                                                          className={`flex items-center justify-center gap-2 px-4 py-2 bg-cyan-600 text-white rounded-lg transition-colors text-xs font-semibold shadow-xs ${isPhaseADisabled ? 'cursor-not-allowed opacity-50 bg-cyan-400' : 'hover:bg-cyan-700 cursor-pointer'}`}
                                                                      >
                                                                          <Upload className="w-4 h-4" />
                                                                          {uploadingEvidence ? 'Enviando...' : 'Enviar Nota Fiscal com Canhoto Assinado'}
                                                                      </button>
                                                                  </div>"""

new_canhoto_upload = """                                                                  <div>
                                                                      <input
                                                                          type="file"
                                                                          accept=".pdf,.jpg,.jpeg,.png"
                                                                          onChange={(e) => handleEvidenceUpload('foto_canhoto_path', e.target.files[0])}
                                                                          disabled={isPhaseADisabled}
                                                                          className="w-full text-sm text-gray-550 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-orange-50 file:text-orange-700 hover:file:bg-orange-100 cursor-pointer border border-gray-300 rounded-lg p-1"
                                                                      />
                                                                  </div>"""

# Replace all
replacements = [
    (old_cargo_reupload, new_cargo_reupload),
    (old_cargo_upload, new_cargo_upload),
    (old_canhoto_reupload, new_canhoto_reupload),
    (old_canhoto_reupload_v2, new_canhoto_reupload),
    (old_canhoto_upload, new_canhoto_upload)
]

replaced_count = 0
for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        replaced_count += 1
        print(f"Replaced successfully a block.")
    else:
        # Try finding without carriage returns, or with normalized whitespace
        # Let's clean carriage returns
        old_normalized = old.replace("\r\n", "\n")
        content_normalized = content.replace("\r\n", "\n")
        if old_normalized in content_normalized:
            content_normalized = content_normalized.replace(old_normalized, new.replace("\r\n", "\n"))
            content = content_normalized
            replaced_count += 1
            print(f"Replaced successfully a block (normalized).")
        else:
            print("Block not found in content!")

with open(filepath, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Total replacements done: {replaced_count}")
