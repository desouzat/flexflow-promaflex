# Database Connection Fix - Port 5433

## Problem
The backend was trying to connect to port 5432, but the Cloud SQL Proxy tunnel is running on port 5433, causing "Connection Refused" errors.

## Root Cause
The default fallback port in `backend/database.py` was hardcoded to 5432.

## Changes Made

### 1. backend/database.py
✅ **Fixed the following issues:**

1. **Moved `load_dotenv()` to the very top** - Now it's called BEFORE any other imports to ensure environment variables are loaded first
2. **Changed default port from 5432 to 5433** - The fallback DATABASE_URL now uses port 5433
3. **Renamed variable for clarity** - Changed `DATABASE_URL` to `SQLALCHEMY_DATABASE_URL` to match SQLAlchemy conventions
4. **Added debug print** - Added `print(f"🔌 Conectando ao banco em: {SQLALCHEMY_DATABASE_URL}")` to show which URL is being used at startup

### Key Changes:
```python
# BEFORE (lines 8-26):
import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
...
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://flexflow_user:flexflow_pass@localhost:5432/flexflow_db"  # ❌ Wrong port
)

# AFTER (lines 8-29):
# CRITICAL: Load environment variables FIRST before any other imports or operations
from dotenv import load_dotenv
load_dotenv()  # ✅ Called FIRST

import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from sqlalchemy.pool import QueuePool
...
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://flexflow_user:flexflow_pass@localhost:5433/flexflow_db"  # ✅ Correct port
)

# Debug print to verify the correct port is being used
print(f"🔌 Conectando ao banco em: {SQLALCHEMY_DATABASE_URL}")  # ✅ Debug output
```

## Verification

### Environment File Status
✅ `backend/.env` exists and contains:
```
DATABASE_URL=postgresql://flexflow_app:Souza%40123@127.0.0.1:5433/flexflow_prod
```

### Code Audit Results
✅ No hardcoded port 5432 found in application code (only in venv libraries)
✅ No other config files with hardcoded database ports
✅ `main.py` has no hardcoded database configuration

## Testing Instructions

1. **Start the backend server:**
   ```bash
   cd backend
   python -m uvicorn main:app --reload
   ```

2. **Look for the debug output in the terminal:**
   ```
   🔌 Conectando ao banco em: postgresql://flexflow_app:Souza%40123@127.0.0.1:5433/flexflow_prod
   ```

3. **Verify the connection:**
   - The port should show **5433** (not 5432)
   - The connection should succeed without "Connection Refused" errors
   - The backend should start successfully

## Expected Behavior

When you start the backend, you should see:
```
🔌 Conectando ao banco em: postgresql://flexflow_app:Souza%40123@127.0.0.1:5433/flexflow_prod
Starting FlexFlow API...
FlexFlow API started successfully
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

## Troubleshooting

If you still see connection errors:

1. **Verify Cloud SQL Proxy is running on port 5433:**
   ```bash
   netstat -an | findstr 5433
   ```

2. **Check if the .env file is being loaded:**
   - The debug print will show which URL is being used
   - If it shows the default URL instead of the one from .env, there may be a path issue

3. **Verify the .env file location:**
   - It should be at `backend/.env`
   - The working directory when running the backend should be the project root or backend folder

## Summary

✅ `load_dotenv()` is now called FIRST before any imports
✅ Default port changed from 5432 to 5433
✅ Debug print added to verify the connection URL
✅ No other hardcoded ports found in the application code
✅ Environment file is correctly configured with port 5433

The backend should now connect successfully to the database through the Cloud SQL Proxy tunnel on port 5433.
