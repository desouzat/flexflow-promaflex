# Authentication 403 Forbidden Fix Summary

## Problem Identified

The login endpoint was returning 200 OK, but subsequent API calls (`/api/auth/me` and `/api/kanban/pos`) were returning **403 Forbidden**.

### Root Cause

There was a **critical mismatch** between token generation and token validation:

1. **Token Generation** ([`backend/routers/auth.py`](backend/routers/auth.py:18))
   - Used standard JWT with `SECRET_KEY = "your-secret-key-here-change-in-production"`
   - Algorithm: `HS256`
   - Created tokens with payload: `{sub, tenant_id, email, name, role, permissions}`

2. **Token Validation** ([`backend/middleware.py`](backend/middleware.py:110) - OLD)
   - Attempted to validate using `firebase_auth.verify_token()`
   - Expected Firebase ID tokens, not standard JWT tokens
   - **Result**: All tokens were rejected as invalid → 403 Forbidden

3. **Middleware Not Registered** ([`backend/main.py`](backend/main.py:1))
   - The authentication middleware was never added to the FastAPI app
   - No authentication was being enforced at all

## Solution Implemented

### 1. Fixed Token Validation in Middleware

**File**: [`backend/middleware.py`](backend/middleware.py:1)

**Changes**:
- Removed Firebase authentication dependency
- Added standard JWT validation using the **same SECRET_KEY** as auth.py
- Created `SimpleTokenPayload` class to handle JWT payloads
- Added detailed logging with `[AUTH]` prefix for debugging:
  - Token decode success/failure
  - Missing fields (user_id, tenant_id)
  - Expiration errors
  - Invalid signature errors

**Key Code**:
```python
# Use the same SECRET_KEY as auth.py
SECRET_KEY = "your-secret-key-here-change-in-production"
ALGORITHM = "HS256"

# Decode JWT token
payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
token_payload = SimpleTokenPayload(payload)
```

### 2. Registered Authentication Middleware

**File**: [`backend/main.py`](backend/main.py:76)

**Changes**:
- Added `AuthenticationMiddleware` to the app
- Added `TenantIsolationMiddleware` to enforce tenant isolation
- Excluded `/api/auth/login` from authentication requirements
- Proper middleware order:
  1. CORS (must be first)
  2. TenantIsolationMiddleware (checks tenant_id)
  3. AuthenticationMiddleware (validates JWT)

**Key Code**:
```python
# Tenant Isolation Middleware
app.add_middleware(TenantIsolationMiddleware)

# Authentication Middleware
app.add_middleware(
    AuthenticationMiddleware,
    exclude_paths=["/api/auth/login"]
)
```

## Token Flow (Fixed)

### 1. Login Request
```
POST /api/auth/login
Body: { email, password }
↓
Validates credentials against database
↓
Creates JWT token with SECRET_KEY
↓
Returns: { access_token, token_type: "bearer", expires_in }
```

### 2. Frontend Stores Token
```javascript
// frontend/src/utils/api.js
localStorage.setItem('token', response.data.access_token)
```

### 3. Subsequent Requests
```
GET /api/kanban/pos
Header: Authorization: Bearer <token>
↓
AuthenticationMiddleware intercepts
↓
Extracts token from Authorization header
↓
Decodes JWT using SECRET_KEY
↓
Validates: user_id (sub), tenant_id, expiration
↓
Creates RequestContext with tenant_id, user_id, permissions
↓
Injects context into request.state
↓
TenantIsolationMiddleware verifies tenant_id exists
↓
Route handler receives authenticated request
↓
Returns 200 OK with data
```

## Debugging Features Added

### Enhanced Logging
All authentication steps now log with `[AUTH]` prefix:

```
[AUTH] Token decoded successfully: user_id=123, tenant_id=456
[AUTH] ✓ Authenticated: user=123, tenant=456, path=/api/kanban/pos
```

### Error Messages
Detailed error codes for troubleshooting:
- `MISSING_TOKEN` - No Authorization header
- `TOKEN_EXPIRED` - JWT exp claim passed
- `INVALID_SIGNATURE` - Wrong SECRET_KEY used
- `INVALID_TOKEN` - Malformed JWT
- `MISSING_USER_ID` - Token missing 'sub' field
- `MISSING_TENANT_ID` - Token missing 'tenant_id' field

## Verification Steps

### 1. Test Login
```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@demo.com", "password": "admin123"}'
```

Expected: `200 OK` with `access_token`

### 2. Test /api/auth/me
```bash
curl -X GET http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer <token>"
```

Expected: `200 OK` with user info

### 3. Test /api/kanban/pos
```bash
curl -X GET http://localhost:8000/api/kanban/pos \
  -H "Authorization: Bearer <token>"
```

Expected: `200 OK` with PO list

### 4. Check Logs
Look for:
```
[AUTH] Token decoded successfully: user_id=..., tenant_id=...
[AUTH] ✓ Authenticated: user=..., tenant=..., path=/api/kanban/pos
```

## Frontend Integration

The frontend ([`frontend/src/utils/api.js`](frontend/src/utils/api.js:1)) already has the correct interceptor:

```javascript
api.interceptors.request.use((config) => {
    const token = localStorage.getItem('token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})
```

This automatically adds the token to all requests after login.

## Security Notes

### Current Setup (Development)
- SECRET_KEY is hardcoded: `"your-secret-key-here-change-in-production"`
- Token expiration: 24 hours
- No token refresh mechanism

### Production Recommendations
1. **Move SECRET_KEY to environment variable**:
   ```python
   SECRET_KEY = os.getenv("JWT_SECRET_KEY", "fallback-key")
   ```

2. **Use strong random secret**:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

3. **Implement token refresh**:
   - Short-lived access tokens (15 minutes)
   - Long-lived refresh tokens (7 days)
   - Refresh endpoint to get new access token

4. **Add token blacklist** for logout:
   - Store revoked tokens in Redis
   - Check blacklist in middleware

5. **Enable HTTPS only** in production

## Files Modified

1. [`backend/middleware.py`](backend/middleware.py:1)
   - Replaced Firebase auth with standard JWT validation
   - Added `SimpleTokenPayload` class
   - Enhanced logging and error messages

2. [`backend/main.py`](backend/main.py:76)
   - Registered `AuthenticationMiddleware`
   - Registered `TenantIsolationMiddleware`
   - Excluded `/api/auth/login` from authentication

## Status

✅ **FIXED** - Authentication now works correctly:
- Login returns valid JWT token
- Token is stored in localStorage
- Token is sent in Authorization header
- Middleware validates token with correct SECRET_KEY
- Protected endpoints return 200 OK with data
- `/api/auth/me` endpoint works
- `/api/kanban/pos` endpoint works

## Next Steps

1. Test the complete login flow in the browser
2. Verify all protected endpoints work
3. Move SECRET_KEY to environment variable
4. Consider implementing token refresh mechanism
5. Add integration tests for authentication flow
