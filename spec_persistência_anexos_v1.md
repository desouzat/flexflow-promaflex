# TECHNICAL SPECIFICATION: ATTACHMENT PERSISTENCE AND PATH SANITIZATION
**Task ID:** FF-HARDENING-001  
**Priority:** Critical  
**Target Agent:** Roo (Dev Agent)  
**Recommended LLM:** Claude Sonnet 4.6 (Thinking)  

---

## 1. OBJECTIVE
Ensure that attachment uploads performed during the Expedition process are successfully persisted into the PostgreSQL database. Specifically, references must be saved inside the `extra_metadata` JSONB column of the `order_items` table. Additionally, the system must sanitize file paths uploaded from Windows operating systems to avoid directory traversal or malformed file names on Linux hosts.

---

## 2. AFFECTED FILES
- `backend/models.py` (For structural reference validation)
- `backend/routers/kanban.py` (Or the respective route file handling file uploads)
- Any utility file for path handling (if applicable)

---

## 3. IMPLEMENTATION DETAILS

### 3.1 Windows Path Sanitization (Item 8.7)
When a file is uploaded via `UploadFile`, its filename might contain full Windows directory paths (e.g., `C:\Users\JohnDoc\file.jpg`) depending on the client browser. On a Linux-based backend, standard `os.path.basename` does not split backslashes (`\`) properly [8].
- **Mandatory Logic:** Use `pathlib.PureWindowsPath` to extract the file's base name safely under any operating system.
```python
from pathlib import PureWindowsPath

def get_safe_filename(filename: str) -> str:
    """
    Safely extracts the file base name, handling both POSIX and Windows paths correctly.
    """
    return PureWindowsPath(filename).name
3.2 JSONB Modification Flagging (Item 8.1)
SQLAlchemy does not automatically detect in-place mutations of PostgreSQL JSONB fields (such as appending an item to an internal list). Therefore, we must explicitly flag the attribute as modified before committing.
Required Persistence Pattern:
code
Python
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime

# 1. Sanitize the incoming filename
safe_filename = get_safe_filename(file.filename)

# 2. Upload file to GCS/Storage and obtain the destination URL
# file_url = await file_service.upload(file) ...

# 3. Retrieve the target item
item = db.query(OrderItem).filter(OrderItem.po_id == po_id).first()
if not item:
    raise HTTPException(status_code=404, detail="Order item not found for this PO")

# 4. Initialize metadata if empty
if not item.extra_metadata:
    item.extra_metadata = {}

if "attachments" not in item.extra_metadata:
    item.extra_metadata["attachments"] = []

# 5. Append new attachment metadata
item.extra_metadata["attachments"].append({
    "filename": safe_filename,
    "url": file_url,
    "timestamp": datetime.utcnow().isoformat()
})

# 6. EXPLICITLY TELL SQLALCHEMY TO MARK THE FIELD AS MODIFIED
flag_modified(item, "extra_metadata")

# 7. Commit changes to PostgreSQL
db.commit()
db.refresh(item)
4. ACCEPTANCE CRITERIA & VALIDATION HARNESS
Before signaling completion, you must fulfill these validations:
Database Persistence: Querying the order_items table after an upload must confirm that the "attachments" array within the extra_metadata JSONB column was successfully appended and saved.
Path Integrity: Ensure that uploading a file with a full Windows path (e.g., C:\MyFiles\test_image.png) stores only the sanitized name test_image.png in the database.
Local Test Harness Execution:
Run the system's test suite (e.g., pytest or equivalent backend tests) to verify no regressions were introduced.
Execute the readiness check script in the backend directory:
code
Bash
python prod_readiness_check.py
Ensure all checks pass successfully.
5. REQUIRED OUTPUT REPORT
After completing the changes, please reply with a report containing:
A summary of the files modified.
The exact code snippet used to resolve the path sanitization and the flag_modified integration.
The output or screenshot proof of the local test harness and prod_readiness_check.py results.