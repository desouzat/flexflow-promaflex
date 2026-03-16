"""
FlexFlow Security Module
Handles Firebase Authentication integration and JWT token validation.
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import jwt
from jwt import PyJWTError
import firebase_admin
from firebase_admin import credentials, auth
from functools import wraps
from fastapi import HTTPException, status


class FirebaseAuthConfig:
    """Configuration for Firebase Authentication"""
    
    def __init__(self):
        self.project_id = os.getenv("FIREBASE_PROJECT_ID")
        self.credentials_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
        self.use_emulator = os.getenv("FIREBASE_AUTH_EMULATOR", "false").lower() == "true"
        self.emulator_host = os.getenv("FIREBASE_AUTH_EMULATOR_HOST", "localhost:9099")
        
        # Initialize Firebase Admin SDK
        if not firebase_admin._apps:
            if self.credentials_path and os.path.exists(self.credentials_path):
                cred = credentials.Certificate(self.credentials_path)
                firebase_admin.initialize_app(cred)
            else:
                # Use default credentials or emulator
                firebase_admin.initialize_app()
        
        if self.use_emulator:
            os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = self.emulator_host


class TokenPayload:
    """Represents the decoded JWT token payload"""
    
    def __init__(self, payload: Dict[str, Any]):
        self.user_id: str = payload.get("sub") or payload.get("uid")
        self.tenant_id: str = payload.get("tenant_id")
        self.email: str = payload.get("email")
        self.permissions: List[str] = payload.get("permissions", [])
        self.role: Optional[str] = payload.get("role")
        self.exp: int = payload.get("exp")
        self.iat: int = payload.get("iat")
        self.raw_payload: Dict[str, Any] = payload
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has a specific permission"""
        return permission in self.permissions
    
    def has_any_permission(self, permissions: List[str]) -> bool:
        """Check if user has any of the specified permissions"""
        return any(perm in self.permissions for perm in permissions)
    
    def has_all_permissions(self, permissions: List[str]) -> bool:
        """Check if user has all of the specified permissions"""
        return all(perm in self.permissions for perm in permissions)
    
    def is_expired(self) -> bool:
        """Check if token is expired"""
        if not self.exp:
            return False
        return datetime.utcnow().timestamp() > self.exp
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "user_id": self.user_id,
            "tenant_id": self.tenant_id,
            "email": self.email,
            "permissions": self.permissions,
            "role": self.role,
            "exp": self.exp,
            "iat": self.iat
        }


class FirebaseAuthService:
    """Service for Firebase Authentication operations"""
    
    def __init__(self):
        self.config = FirebaseAuthConfig()
    
    async def verify_token(self, token: str) -> TokenPayload:
        """
        Verify Firebase ID token and return decoded payload
        
        Args:
            token: Firebase ID token (JWT)
            
        Returns:
            TokenPayload with user information
            
        Raises:
            HTTPException: If token is invalid or expired
        """
        try:
            # Verify the token with Firebase Admin SDK
            decoded_token = auth.verify_id_token(token, check_revoked=True)
            
            # Extract tenant_id from custom claims
            tenant_id = decoded_token.get("tenant_id")
            if not tenant_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Token missing tenant_id claim"
                )
            
            # Create TokenPayload
            payload = TokenPayload(decoded_token)
            
            # Validate required fields
            if not payload.user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Token missing user_id"
                )
            
            return payload
            
        except auth.ExpiredIdTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except auth.RevokedIdTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except auth.InvalidIdTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token verification failed: {str(e)}",
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    async def set_custom_claims(self, user_id: str, claims: Dict[str, Any]) -> None:
        """
        Set custom claims for a user (tenant_id, permissions, role)
        
        Args:
            user_id: Firebase user ID
            claims: Dictionary of custom claims to set
        """
        try:
            auth.set_custom_user_claims(user_id, claims)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to set custom claims: {str(e)}"
            )
    
    async def get_user(self, user_id: str) -> Dict[str, Any]:
        """
        Get user information from Firebase
        
        Args:
            user_id: Firebase user ID
            
        Returns:
            User information dictionary
        """
        try:
            user = auth.get_user(user_id)
            return {
                "uid": user.uid,
                "email": user.email,
                "display_name": user.display_name,
                "photo_url": user.photo_url,
                "disabled": user.disabled,
                "custom_claims": user.custom_claims or {}
            }
        except auth.UserNotFoundError:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to get user: {str(e)}"
            )
    
    async def create_user(
        self,
        email: str,
        password: str,
        tenant_id: str,
        permissions: List[str],
        role: Optional[str] = None,
        display_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a new user with custom claims
        
        Args:
            email: User email
            password: User password
            tenant_id: Tenant ID for multi-tenancy
            permissions: List of permissions
            role: Optional role name
            display_name: Optional display name
            
        Returns:
            Created user information
        """
        try:
            # Create user
            user = auth.create_user(
                email=email,
                password=password,
                display_name=display_name
            )
            
            # Set custom claims
            custom_claims = {
                "tenant_id": tenant_id,
                "permissions": permissions,
                "role": role
            }
            auth.set_custom_user_claims(user.uid, custom_claims)
            
            return {
                "uid": user.uid,
                "email": user.email,
                "display_name": user.display_name,
                "tenant_id": tenant_id,
                "permissions": permissions,
                "role": role
            }
        except auth.EmailAlreadyExistsError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"User with email {email} already exists"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create user: {str(e)}"
            )


class PermissionChecker:
    """Helper class for permission checking decorators"""
    
    @staticmethod
    def require_permission(permission: str):
        """
        Decorator to require a specific permission
        
        Usage:
            @require_permission("po.create")
            async def create_po(context: RequestContext):
                ...
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Extract context from kwargs
                context = kwargs.get("context")
                if not context or not hasattr(context, "token_payload"):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
                
                if not context.token_payload.has_permission(permission):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied: {permission} required"
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def require_any_permission(permissions: List[str]):
        """
        Decorator to require any of the specified permissions
        
        Usage:
            @require_any_permission(["po.read", "po.update"])
            async def view_po(context: RequestContext):
                ...
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                context = kwargs.get("context")
                if not context or not hasattr(context, "token_payload"):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
                
                if not context.token_payload.has_any_permission(permissions):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied: one of {permissions} required"
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator
    
    @staticmethod
    def require_all_permissions(permissions: List[str]):
        """
        Decorator to require all of the specified permissions
        
        Usage:
            @require_all_permissions(["po.read", "po.update"])
            async def update_po(context: RequestContext):
                ...
        """
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                context = kwargs.get("context")
                if not context or not hasattr(context, "token_payload"):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required"
                    )
                
                if not context.token_payload.has_all_permissions(permissions):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied: all of {permissions} required"
                    )
                
                return await func(*args, **kwargs)
            return wrapper
        return decorator


# Global instance
firebase_auth = FirebaseAuthService()

# Export permission decorators
require_permission = PermissionChecker.require_permission
require_any_permission = PermissionChecker.require_any_permission
require_all_permissions = PermissionChecker.require_all_permissions
