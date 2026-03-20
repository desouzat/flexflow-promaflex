"""
FlexFlow Authentication Schemas
Pydantic schemas for authentication and authorization.
"""

from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime


class LoginRequest(BaseModel):
    """Login request schema"""
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=6, description="User password")


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    user: Optional[dict] = Field(None, description="User information")


class UserInfo(BaseModel):
    """User information from token"""
    id: str = Field(..., description="User ID")
    tenant_id: str = Field(..., description="Tenant ID")
    email: str = Field(..., description="User email")
    name: str = Field(..., description="User name")
    role: str = Field(..., description="User role")
    permissions: List[str] = Field(default_factory=list, description="User permissions")
    is_active: bool = Field(default=True, description="User active status")


class MeResponse(BaseModel):
    """Current user information response"""
    user: UserInfo = Field(..., description="User information")
    tenant_name: Optional[str] = Field(None, description="Tenant name")
    authenticated_at: datetime = Field(..., description="Authentication timestamp")
