"""
FlexFlow Middleware
Handles JWT extraction, validation, and context injection for multi-tenant requests.
"""

from typing import Optional, Callable
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging
import jwt
import traceback

# HARDCODED SECRET_KEY for diagnostic purposes - MUST match auth.py exactly
SECRET_KEY = "your-secret-key-here-change-in-production"
ALGORITHM = "HS256"


logger = logging.getLogger(__name__)


class SimpleTokenPayload:
    """Simplified token payload for JWT tokens"""
    
    def __init__(self, payload: dict):
        self.user_id: str = payload.get("sub")
        self.tenant_id: str = payload.get("tenant_id")
        self.email: str = payload.get("email")
        self.name: str = payload.get("name", "User")
        self.role: str = payload.get("role", "user")
        self.permissions: list[str] = payload.get("permissions", [])
        self.exp: int = payload.get("exp")
        self.iat: int = payload.get("iat")
        self.raw_payload: dict = payload
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission"""
        return permission in self.permissions
    
    def has_any_permission(self, permissions: list[str]) -> bool:
        """Check if user has any of the specified permissions"""
        return any(perm in self.permissions for perm in permissions)
    
    def has_all_permissions(self, permissions: list[str]) -> bool:
        """Check if user has all of the specified permissions"""
        return all(perm in self.permissions for perm in permissions)


class RequestContext:
    """
    Request context that holds tenant_id, user_id, and token payload.
    This is injected into the request state for use in route handlers.
    """
    
    def __init__(
        self,
        tenant_id: str,
        user_id: str,
        token_payload: SimpleTokenPayload,
        ip_address: Optional[str] = None
    ):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.token_payload = token_payload
        self.ip_address = ip_address
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission"""
        return self.token_payload.has_permission(permission)
    
    def has_any_permission(self, permissions: list[str]) -> bool:
        """Check if user has any of the specified permissions"""
        return self.token_payload.has_any_permission(permissions)
    
    def has_all_permissions(self, permissions: list[str]) -> bool:
        """Check if user has all of the specified permissions"""
        return self.token_payload.has_all_permissions(permissions)
    
    def to_dict(self) -> dict:
        """Convert context to dictionary for logging/audit"""
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "email": self.token_payload.email,
            "role": self.token_payload.role,
            "permissions": self.token_payload.permissions
        }


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts and validates JWT tokens from requests.
    Injects tenant_id and user_id into request context.
    """
    
    # Paths that don't require authentication
    PUBLIC_PATHS = [
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/",
        "/api/auth/login",  # Login endpoint must be public
        "/api/auth/me",     # Me endpoint must be public to avoid redirect loops
    ]
    
    def __init__(self, app: ASGIApp, exclude_paths: Optional[list[str]] = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or []
        self.exclude_paths.extend(self.PUBLIC_PATHS)
    
    async def dispatch(self, request: Request, call_next: Callable):
        """
        Process each request:
        1. Check if path requires authentication
        2. Extract JWT token from Authorization header
        3. Validate token using same SECRET_KEY as auth.py
        4. Inject context into request.state
        5. Continue to route handler
        """
        
        # PROTOCOL STEP 1: Print ALL headers for every request
        print("\n" + "🔍"*40)
        print(f"[HEADERS] Path: {request.url.path}")
        print(f"[HEADERS] Method: {request.method}")
        print("[HEADERS] All Headers:")
        for header_name, header_value in request.headers.items():
            if header_name.lower() == "authorization":
                # Show first/last chars of token for security
                if len(header_value) > 100:
                    print(f"  - {header_name}: {header_value[:50]}...{header_value[-30:]}")
                else:
                    print(f"  - {header_name}: {header_value}")
            else:
                print(f"  - {header_name}: {header_value}")
        print("🔍"*40 + "\n")
        
        # Skip authentication for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)
        
        try:
            # Extract token from Authorization header
            token = self._extract_token(request)
            
            if not token:
                logger.warning(f"[AUTH] Missing token for path: {request.url.path}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Missing authentication token",
                        "error_code": "MISSING_TOKEN"
                    },
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # DEBUG: Print token info before decoding
            print("\n" + "="*80)
            print(f"[MIDDLEWARE] Attempting to decode token for path: {request.url.path}")
            print(f"  - Token (first 50 chars): {token[:50]}...")
            print(f"  - Token (last 50 chars): ...{token[-50:]}")
            print(f"  - Token length: {len(token)} chars")
            print(f"  - SECRET_KEY (first 20 chars): {SECRET_KEY[:20]}...")
            print(f"  - ALGORITHM: {ALGORITHM}")
            print("="*80 + "\n")
            
            # Decode and verify JWT token using the same SECRET_KEY as auth.py
            try:
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                
                # DEBUG: Print decoded payload
                print("\n" + "="*80)
                print("[MIDDLEWARE] Token decoded SUCCESSFULLY:")
                print(f"  - sub (user_id): {payload.get('sub')}")
                print(f"  - tenant_id: {payload.get('tenant_id')}")
                print(f"  - email: {payload.get('email')}")
                print(f"  - name: {payload.get('name')}")
                print(f"  - role: {payload.get('role')}")
                print(f"  - permissions: {payload.get('permissions')}")
                print(f"  - exp: {payload.get('exp')}")
                print(f"  - iat: {payload.get('iat')}")
                print("="*80 + "\n")
                
                logger.debug(f"[AUTH] Token decoded successfully: user_id={payload.get('sub')}, tenant_id={payload.get('tenant_id')}")
            except jwt.ExpiredSignatureError as e:
                print("\n" + "="*80)
                print("[MIDDLEWARE] JWT ERROR - Token EXPIRED:")
                print(f"  - Error: {str(e)}")
                print(f"  - Path: {request.url.path}")
                print("="*80 + "\n")
                logger.warning(f"[AUTH] Token expired for path: {request.url.path}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Token has expired",
                        "error_code": "TOKEN_EXPIRED"
                    },
                    headers={"WWW-Authenticate": "Bearer"}
                )
            except jwt.InvalidSignatureError as e:
                print("\n" + "="*80)
                print("[MIDDLEWARE] JWT ERROR - INVALID SIGNATURE:")
                print(f"  - Error: {str(e)}")
                print(f"  - Path: {request.url.path}")
                print(f"  - This means the SECRET_KEY used to decode doesn't match the one used to encode!")
                print("="*80 + "\n")
                logger.warning(f"[AUTH] Invalid token signature for path: {request.url.path}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Invalid token signature",
                        "error_code": "INVALID_SIGNATURE"
                    },
                    headers={"WWW-Authenticate": "Bearer"}
                )
            except jwt.DecodeError as e:
                print("\n" + "="*80)
                print("[MIDDLEWARE] JWT ERROR - DECODE ERROR:")
                print(f"  - Error: {str(e)}")
                print(f"  - Path: {request.url.path}")
                print(f"  - Token might be malformed or corrupted")
                print("="*80 + "\n")
                logger.warning(f"[AUTH] JWT decode error: {str(e)} for path: {request.url.path}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": f"Could not decode token: {str(e)}",
                        "error_code": "DECODE_ERROR"
                    },
                    headers={"WWW-Authenticate": "Bearer"}
                )
            except jwt.JWTError as e:
                print("\n" + "="*80)
                print("[MIDDLEWARE] JWT ERROR - GENERIC JWT ERROR:")
                print(f"  - Error type: {type(e).__name__}")
                print(f"  - Error: {str(e)}")
                print(f"  - Path: {request.url.path}")
                print("="*80 + "\n")
                logger.warning(f"[AUTH] JWT error: {str(e)} for path: {request.url.path}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": f"Could not validate credentials: {str(e)}",
                        "error_code": "INVALID_TOKEN"
                    },
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Create token payload
            token_payload = SimpleTokenPayload(payload)
            
            # PROTOCOL STEP 2: Type comparison debug - tenant_id
            print("\n" + "🔬"*40)
            print("[TYPE CHECK] Analyzing tenant_id from token:")
            print(f"  - Raw tenant_id from payload: {payload.get('tenant_id')}")
            print(f"  - Type: {type(payload.get('tenant_id'))}")
            print(f"  - token_payload.tenant_id: {token_payload.tenant_id}")
            print(f"  - Type: {type(token_payload.tenant_id)}")
            print(f"  - Converted to string: '{str(token_payload.tenant_id)}'")
            print("🔬"*40 + "\n")
            
            # Validate required fields
            if not token_payload.user_id:
                print("\n" + "="*80)
                print("[MIDDLEWARE] VALIDATION ERROR - Missing user_id:")
                print(f"  - Path: {request.url.path}")
                print(f"  - Payload: {payload}")
                print("="*80 + "\n")
                logger.error(f"[AUTH] Token missing user_id (sub) for path: {request.url.path}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Token missing user_id",
                        "error_code": "MISSING_USER_ID"
                    },
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            if not token_payload.tenant_id:
                print("\n" + "="*80)
                print("[MIDDLEWARE] VALIDATION ERROR - Missing tenant_id:")
                print(f"  - Path: {request.url.path}")
                print(f"  - user_id: {token_payload.user_id}")
                print(f"  - Payload: {payload}")
                print("="*80 + "\n")
                logger.error(f"[AUTH] Token missing tenant_id for path: {request.url.path}")
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "detail": "Token missing tenant_id",
                        "error_code": "MISSING_TENANT_ID"
                    }
                )
            
            # Extract client IP address
            ip_address = self._get_client_ip(request)
            
            # PROTOCOL STEP 2: Force tenant_id and user_id to strings for consistency
            tenant_id_str = str(token_payload.tenant_id)
            user_id_str = str(token_payload.user_id)
            
            print("\n" + "🔄"*40)
            print("[STRING CONVERSION] Forcing types to string:")
            print(f"  - tenant_id: {tenant_id_str} (type: {type(tenant_id_str)})")
            print(f"  - user_id: {user_id_str} (type: {type(user_id_str)})")
            print("🔄"*40 + "\n")
            
            # Create request context with string-converted IDs
            context = RequestContext(
                tenant_id=tenant_id_str,
                user_id=user_id_str,
                token_payload=token_payload,
                ip_address=ip_address
            )
            
            # Inject context into request state
            request.state.context = context
            request.state.tenant_id = context.tenant_id
            request.state.user_id = context.user_id
            
            # Log authentication success
            logger.info(
                f"[AUTH] ✓ Authenticated: user={context.user_id}, "
                f"tenant={context.tenant_id}, path={request.url.path}"
            )
            
            print("\n" + "✅"*40)
            print("[AUTH SUCCESS] Context injected successfully:")
            print(f"  - tenant_id: {context.tenant_id}")
            print(f"  - user_id: {context.user_id}")
            print(f"  - Proceeding to next middleware/handler...")
            print("✅"*40 + "\n")
            
            # Continue to route handler
            response = await call_next(request)
            
            # Add tenant context to response headers (for debugging)
            response.headers["X-Tenant-ID"] = context.tenant_id
            response.headers["X-User-ID"] = context.user_id
            
            return response
            
        except HTTPException as e:
            # Handle authentication errors
            logger.warning(
                f"[AUTH] Authentication failed: {e.detail}, path={request.url.path}"
            )
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "detail": e.detail,
                    "error_code": "AUTHENTICATION_FAILED"
                },
                headers=e.headers or {}
            )
        except Exception as e:
            # PROTOCOL STEP 3: Detailed exception handling with traceback
            print("\n" + "💥"*40)
            print("[EXCEPTION] Unexpected error in AuthenticationMiddleware:")
            print(f"  - Error type: {type(e).__name__}")
            print(f"  - Error message: {str(e)}")
            print(f"  - Path: {request.url.path}")
            print("\n[TRACEBACK]:")
            print(traceback.format_exc())
            print("💥"*40 + "\n")
            
            logger.error(
                f"[AUTH] Unexpected error in authentication middleware: {str(e)}",
                exc_info=True
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": f"Internal server error during authentication: {str(e)}",
                    "error_code": "INTERNAL_ERROR",
                    "error_type": type(e).__name__
                }
            )
    
    def _is_public_path(self, path: str) -> bool:
        """Check if path is public and doesn't require authentication"""
        return any(path.startswith(public_path) for public_path in self.exclude_paths)
    
    def _extract_token(self, request: Request) -> Optional[str]:
        """
        Extract JWT token from Authorization header.
        Expected format: "Bearer <token>"
        """
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            return None
        
        parts = auth_header.split()
        
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return None
        
        return parts[1]
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request.
        Checks X-Forwarded-For header first (for proxies), then falls back to client.host
        """
        # Check X-Forwarded-For header (for requests through proxies/load balancers)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, take the first one
            return forwarded_for.split(",")[0].strip()
        
        # Check X-Real-IP header
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fall back to direct client IP
        if request.client:
            return request.client.host
        
        return "unknown"


class TenantIsolationMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces tenant isolation.
    Ensures all database queries are scoped to the authenticated tenant.
    """
    
    async def dispatch(self, request: Request, call_next: Callable):
        """
        Verify tenant context exists and is valid before processing request.
        """
        
        # PROTOCOL STEP 3: Wrap entire middleware in try-except
        try:
            # Skip for public paths
            if self._is_public_path(request.url.path):
                return await call_next(request)
            
            # DEBUG: Log tenant isolation check
            print("\n" + "="*80)
            print(f"[TENANT ISOLATION] Checking tenant context for path: {request.url.path}")
            print(f"  - Has request.state.context: {hasattr(request.state, 'context')}")
            print(f"  - Has request.state.tenant_id: {hasattr(request.state, 'tenant_id')}")
            
            # Verify context was injected by AuthenticationMiddleware
            if not hasattr(request.state, "context"):
                print(f"  - ❌ MISSING CONTEXT - AuthenticationMiddleware did not inject context!")
                print("="*80 + "\n")
                logger.error(
                    f"Tenant isolation check failed: missing context, path={request.url.path}"
                )
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "detail": "Request context not initialized",
                        "error_code": "MISSING_CONTEXT"
                    }
                )
            
            context: RequestContext = request.state.context
            
            print(f"  - ✓ Context exists")
            print(f"  - tenant_id: {context.tenant_id if context.tenant_id else '❌ EMPTY'}")
            print(f"  - tenant_id type: {type(context.tenant_id)}")
            print(f"  - user_id: {context.user_id if context.user_id else '❌ EMPTY'}")
            print(f"  - user_id type: {type(context.user_id)}")
            print("="*80 + "\n")
            
            # Validate tenant_id
            if not context.tenant_id:
                logger.error(
                    f"Tenant isolation check failed: missing tenant_id, user={context.user_id}"
                )
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "detail": "Tenant ID not found in token",
                        "error_code": "MISSING_TENANT_ID"
                    }
                )
            
            # Log tenant access
            logger.debug(
                f"Tenant access: tenant={context.tenant_id}, "
                f"user={context.user_id}, path={request.url.path}"
            )
            
            print("\n" + "🚀"*40)
            print("[TENANT ISOLATION] All checks passed, proceeding to handler...")
            print("🚀"*40 + "\n")
            
            # Continue to route handler
            return await call_next(request)
            
        except Exception as e:
            # PROTOCOL STEP 3: Detailed exception handling with traceback
            print("\n" + "💥"*40)
            print("[EXCEPTION] Unexpected error in TenantIsolationMiddleware:")
            print(f"  - Error type: {type(e).__name__}")
            print(f"  - Error message: {str(e)}")
            print(f"  - Path: {request.url.path}")
            print("\n[TRACEBACK]:")
            print(traceback.format_exc())
            print("💥"*40 + "\n")
            
            logger.error(
                f"[TENANT] Unexpected error in tenant isolation middleware: {str(e)}",
                exc_info=True
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": f"Internal server error during tenant isolation: {str(e)}",
                    "error_code": "INTERNAL_ERROR",
                    "error_type": type(e).__name__
                }
            )
    
    def _is_public_path(self, path: str) -> bool:
        """Check if path is public"""
        return any(
            path.startswith(public_path)
            for public_path in AuthenticationMiddleware.PUBLIC_PATHS
        )


def get_request_context(request: Request) -> RequestContext:
    """
    Helper function to extract RequestContext from request.
    Use this in route handlers to access tenant_id, user_id, and permissions.
    
    Usage:
        @app.get("/api/pos")
        async def list_pos(request: Request):
            context = get_request_context(request)
            # Use context.tenant_id, context.user_id, etc.
    """
    if not hasattr(request.state, "context"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    return request.state.context


def require_tenant_access(request: Request, tenant_id: str) -> None:
    """
    Verify that the authenticated user has access to the specified tenant.
    Raises HTTPException if access is denied.
    
    Usage:
        @app.get("/api/tenants/{tenant_id}/pos")
        async def list_tenant_pos(request: Request, tenant_id: str):
            require_tenant_access(request, tenant_id)
            # Continue with tenant-specific logic
    """
    context = get_request_context(request)
    
    if context.tenant_id != tenant_id:
        logger.warning(
            f"Tenant access denied: user={context.user_id}, "
            f"user_tenant={context.tenant_id}, requested_tenant={tenant_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied to tenant {tenant_id}"
        )


def require_permission(request: Request, permission: str) -> None:
    """
    Verify that the authenticated user has the specified permission.
    Raises HTTPException if permission is denied.
    
    Usage:
        @app.post("/api/pos")
        async def create_po(request: Request):
            require_permission(request, "po.create")
            # Continue with creation logic
    """
    context = get_request_context(request)
    
    if not context.has_permission(permission):
        logger.warning(
            f"Permission denied: user={context.user_id}, "
            f"required={permission}, has={context.token_payload.permissions}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {permission} required"
        )


def require_any_permission(request: Request, permissions: list[str]) -> None:
    """
    Verify that the authenticated user has at least one of the specified permissions.
    Raises HTTPException if none of the permissions are granted.
    """
    context = get_request_context(request)
    
    if not context.has_any_permission(permissions):
        logger.warning(
            f"Permission denied: user={context.user_id}, "
            f"required_any={permissions}, has={context.token_payload.permissions}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: one of {permissions} required"
        )


def require_all_permissions(request: Request, permissions: list[str]) -> None:
    """
    Verify that the authenticated user has all of the specified permissions.
    Raises HTTPException if any permission is missing.
    """
    context = get_request_context(request)
    
    if not context.has_all_permissions(permissions):
        logger.warning(
            f"Permission denied: user={context.user_id}, "
            f"required_all={permissions}, has={context.token_payload.permissions}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: all of {permissions} required"
        )
