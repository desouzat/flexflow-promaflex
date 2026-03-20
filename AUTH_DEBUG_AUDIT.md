# 🔍 AUTH 403 DEBUG AUDIT - Technical Investigation

**Date**: 2026-03-19  
**Issue**: 403 Forbidden on `/api/auth/me` persists even after successful login  
**Status**: ⚙️ Debugging instrumentation added

---

## 🎯 Objective

Perform a technical audit to identify why JWT tokens generated during login are being rejected by the middleware, causing 403 Forbidden errors.

---

## 🔧 Changes Implemented

### 1. **SECRET_KEY Verification** ✅

**Location**: [`backend/routers/auth.py:18`](backend/routers/auth.py:18) and [`backend/middleware.py:15`](backend/middleware.py:15)

**Finding**: Both files use the **SAME** hardcoded SECRET_KEY:
```python
SECRET_KEY = "your-secret-key-here-change-in-production"
ALGORITHM = "HS256"
```

**Status**: ✅ SECRET_KEY is identical in both files - this is NOT the issue.

---

### 2. **Token Generation Debug Logging** 🔍

**Location**: [`backend/routers/auth.py:168-203`](backend/routers/auth.py:168)

**Added Debug Prints**:
```python
# BEFORE encoding:
- sub (user_id)
- tenant_id
- email
- name
- role
- permissions
- SECRET_KEY (first 20 chars)
- ALGORITHM

# AFTER encoding:
- Token (first 50 chars)
- Token (last 50 chars)
- Token length
- Expires in minutes
```

**Purpose**: Confirm that `user_id` and `tenant_id` are present in the token payload before encoding.

---

### 3. **Token Validation Debug Logging** 🔍

**Location**: [`backend/middleware.py:125-230`](backend/middleware.py:125)

**Added Debug Prints**:

#### A. Before Decoding:
```python
- Token (first 50 chars)
- Token (last 50 chars)
- Token length
- SECRET_KEY (first 20 chars)
- ALGORITHM
```

#### B. After Successful Decoding:
```python
- sub (user_id)
- tenant_id
- email
- name
- role
- permissions
- exp (expiration)
- iat (issued at)
```

#### C. JWT Error Handling (Enhanced):
- **ExpiredSignatureError**: Token has expired
- **InvalidSignatureError**: SECRET_KEY mismatch between encoding and decoding
- **DecodeError**: Token is malformed or corrupted
- **Generic JWTError**: Other JWT validation errors

Each error now prints:
- Error type
- Error message
- Request path
- Diagnostic hints

---

### 4. **Validation Error Debug Logging** 🔍

**Location**: [`backend/middleware.py:179-220`](backend/middleware.py:179)

**Added Debug Prints**:

#### Missing user_id:
```python
- Path
- Full payload
```

#### Missing tenant_id:
```python
- Path
- user_id (if present)
- Full payload
```

**Purpose**: Identify if required claims are missing from the decoded token.

---

### 5. **Public Paths Configuration** ✅

**Location**: [`backend/middleware.py:98-104`](backend/middleware.py:98)

**Added**: `/api/auth/login` to PUBLIC_PATHS list

**Before**:
```python
PUBLIC_PATHS = [
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/",
]
```

**After**:
```python
PUBLIC_PATHS = [
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
    "/",
    "/api/auth/login",  # Login endpoint must be public
]
```

**Note**: [`main.py:101`](backend/main.py:101) already had this in `exclude_paths`, but adding it to the middleware's PUBLIC_PATHS ensures consistency.

---

## 📊 Expected Debug Output

### On Login (POST /api/auth/login):

```
================================================================================
[AUTH LOGIN] Token Payload BEFORE encoding:
  - sub (user_id): <uuid>
  - tenant_id: <uuid>
  - email: user@example.com
  - name: User Name
  - role: admin
  - permissions: ['po.create', 'po.read', ...]
  - SECRET_KEY (first 20 chars): your-secret-key-here
  - ALGORITHM: HS256
================================================================================

================================================================================
[AUTH LOGIN] Token GENERATED:
  - Token (first 50 chars): eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOi...
  - Token (last 50 chars): ...xMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0Ij
  - Token length: 456 chars
  - Expires in: 1440 minutes
================================================================================
```

### On Protected Endpoint (GET /api/auth/me):

#### Success Case:
```
================================================================================
[MIDDLEWARE] Attempting to decode token for path: /api/auth/me
  - Token (first 50 chars): eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOi...
  - Token (last 50 chars): ...xMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0Ij
  - Token length: 456 chars
  - SECRET_KEY (first 20 chars): your-secret-key-here
  - ALGORITHM: HS256
================================================================================

================================================================================
[MIDDLEWARE] Token decoded SUCCESSFULLY:
  - sub (user_id): <uuid>
  - tenant_id: <uuid>
  - email: user@example.com
  - name: User Name
  - role: admin
  - permissions: ['po.create', 'po.read', ...]
  - exp: 1234567890
  - iat: 1234567890
================================================================================
```

#### Error Case (Invalid Signature):
```
================================================================================
[MIDDLEWARE] JWT ERROR - INVALID SIGNATURE:
  - Error: Signature verification failed
  - Path: /api/auth/me
  - This means the SECRET_KEY used to decode doesn't match the one used to encode!
================================================================================
```

#### Error Case (Missing Claims):
```
================================================================================
[MIDDLEWARE] VALIDATION ERROR - Missing tenant_id:
  - Path: /api/auth/me
  - user_id: <uuid>
  - Payload: {'sub': '<uuid>', 'email': 'user@example.com', ...}
================================================================================
```

---

## 🧪 Testing Instructions

### 1. **Restart the Server**
The server should auto-reload with the new debug code.

### 2. **Perform Login**
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@flexflow.com", "password": "your-password"}'
```

**Expected**: Debug output showing token generation with all claims.

### 3. **Call Protected Endpoint**
```bash
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer <token-from-login>"
```

**Expected**: Debug output showing token decoding and validation.

### 4. **Analyze Terminal Output**
Look for:
- ✅ Token payload contains `sub` and `tenant_id` before encoding
- ✅ Token is generated successfully
- ✅ Token is decoded successfully with same SECRET_KEY
- ✅ Decoded payload contains `sub` and `tenant_id`
- ❌ Any JWT errors (signature, expiration, decode)
- ❌ Any validation errors (missing claims)

---

## 🔍 Diagnostic Checklist

- [x] **SECRET_KEY Match**: Verified both files use identical SECRET_KEY
- [x] **Token Payload Logging**: Added pre-encoding payload inspection
- [x] **Token Generation Logging**: Added post-encoding token inspection
- [x] **Token Decoding Logging**: Added pre-decoding token inspection
- [x] **Decoded Payload Logging**: Added post-decoding payload inspection
- [x] **JWT Error Logging**: Enhanced error handling with detailed diagnostics
- [x] **Validation Error Logging**: Added missing claims detection
- [x] **Public Paths**: Ensured `/api/auth/login` is public
- [ ] **Terminal Output Analysis**: Waiting for user to test and provide output

---

## 🎯 Next Steps

1. **Test the login flow** in the frontend or via curl
2. **Capture the terminal output** showing the debug prints
3. **Analyze the output** to identify:
   - Is the token being generated with correct claims?
   - Is the token being decoded with the same SECRET_KEY?
   - Are there any JWT errors?
   - Are there any missing claims?
4. **Apply the fix** based on the diagnostic output

---

## 📝 Notes

- All debug prints use `print()` to ensure they appear in the terminal immediately
- Debug prints are wrapped in `=` borders for easy identification
- Token values are truncated (first/last 50 chars) for security
- SECRET_KEY is only shown partially (first 20 chars) for security
- This is **temporary debugging code** and should be removed or converted to proper logging after the issue is resolved

---

## 🚨 Known Issues

1. **UnicodeEncodeError on Shutdown**: The emoji in the shutdown message causes encoding errors on Windows. This is cosmetic and doesn't affect functionality.

---

## 📚 Related Files

- [`backend/routers/auth.py`](backend/routers/auth.py) - JWT token generation
- [`backend/middleware.py`](backend/middleware.py) - JWT token validation
- [`backend/main.py`](backend/main.py) - Middleware configuration
- [`backend/security.py`](backend/security.py) - Firebase auth (not currently used)

---

**Status**: ⏳ Waiting for test results to identify the root cause.
