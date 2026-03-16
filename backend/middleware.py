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

from backend.security import firebase_auth, TokenPayload


logger = logging.getLogger(__name__)


class RequestContext:
    """
    Request context that holds tenant_id, user_id, and token payload.
    This is injected into the request state for use in route handlers.
    """
    
    def __init__(
        self,
        tenant_id: str,
        user_id: str,
        token_payload: TokenPayload,
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
        3. Validate token with Firebase
        4. Inject context into request.state
        5. Continue to route handler
        """
        
        # Skip authentication for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)
        
        try:
            # Extract token from Authorization header
            token = self._extract_token(request)
            
            if not token:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "detail": "Missing authentication token",
                        "error_code": "MISSING_TOKEN"
                    },
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            # Verify token with Firebase
            token_payload = await firebase_auth.verify_token(token)
            
            # Extract client IP address
            ip_address = self._get_client_ip(request)
            
            # Create request context
            context = RequestContext(
                tenant_id=token_payload.tenant_id,
                user_id=token_payload.user_id,
                token_payload=token_payload,
                ip_address=ip_address
            )
            
            # Inject context into request state
            request.state.context = context
            request.state.tenant_id = context.tenant_id
            request.state.user_id = context.user_id
            
            # Log authentication success
            logger.info(
                f"Authenticated request: user={context.user_id}, "
                f"tenant={context.tenant_id}, path={request.url.path}"
            )
            
            # Continue to route handler
            response = await call_next(request)
            
            # Add tenant context to response headers (for debugging)
            response.headers["X-Tenant-ID"] = context.tenant_id
            response.headers["X-User-ID"] = context.user_id
            
            return response
            
        except HTTPException as e:
            # Handle authentication errors
            logger.warning(
                f"Authentication failed: {e.detail}, path={request.url.path}"
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
            # Handle unexpected errors
            logger.error(
                f"Unexpected error in authentication middleware: {str(e)}",
                exc_info=True
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "Internal server error during authentication",
                    "error_code": "INTERNAL_ERROR"
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
        
        # Skip for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)
        
        # Verify context was injected by AuthenticationMiddleware
        if not hasattr(request.state, "context"):
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
        
        # Continue to route handler
        return await call_next(request)
    
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
