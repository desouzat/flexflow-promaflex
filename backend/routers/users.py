"""
User Management Router
RBAC-restricted endpoints for managing users (MASTER/ADMIN only)
"""

from fastapi import APIRouter, Request, HTTPException, status, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
from typing import List
from pydantic import BaseModel, EmailStr
import uuid

from backend.database import get_db
from backend.models import User
from backend.middleware import get_request_context
from backend.routers.auth import get_password_hash

router = APIRouter(prefix="/api/users", tags=["User Management"])


# ============================================================================
# SCHEMAS
# ============================================================================

class UserCreate(BaseModel):
    """Schema for creating a new user"""
    username: str
    email: EmailStr
    password: str
    role: str  # 'master', 'admin', 'user'
    area: str  # 'Comercial', 'PCP', 'Produção', etc.


class UserResponse(BaseModel):
    """Schema for user response"""
    id: str
    username: str
    email: str
    role: str
    area: str
    tenant_id: str
    created_at: str
    
    class Config:
        from_attributes = True


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def require_master_or_admin(request: Request):
    """Verify that the user is MASTER or ADMIN"""
    context = get_request_context(request)
    
    if context.token_payload.role not in ['master', 'admin']:
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        print(f"{timestamp} [RBAC] Access denied: user {context.user_id} (role: {context.token_payload.role}) attempted to access user management")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only MASTER or ADMIN users can manage users."
        )
    
    return context


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/", response_model=List[UserResponse])
async def list_users(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    List all users in the tenant (MASTER/ADMIN only)
    """
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    context = require_master_or_admin(request)
    
    print(f"{timestamp} [USER MANAGEMENT] Listing users for tenant: {context.tenant_id}")
    
    try:
        # Query users in the same tenant
        stmt = select(User).where(User.tenant_id == context.tenant_id).order_by(User.created_at.desc())
        result = db.execute(stmt)
        users = result.scalars().all()
        
        print(f"{timestamp} [USER MANAGEMENT] Found {len(users)} users")
        
        # Convert to response format
        user_list = []
        for user in users:
            user_list.append(UserResponse(
                id=str(user.id),
                username=user.username,
                email=user.email,
                role=user.role,
                area=user.area or "N/A",
                tenant_id=str(user.tenant_id),
                created_at=user.created_at.isoformat() if user.created_at else ""
            ))
        
        return user_list
        
    except Exception as e:
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        print(f"{timestamp} [ERROR] Failed to list users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}"
        )


@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Create a new user (MASTER/ADMIN only)
    """
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    context = require_master_or_admin(request)
    
    print(f"{timestamp} [USER MANAGEMENT] Creating user: {user_data.username} (role: {user_data.role})")
    
    try:
        # Validate role
        valid_roles = ['master', 'admin', 'user']
        if user_data.role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
            )
        
        # Check if username already exists in tenant
        stmt = select(User).where(
            User.tenant_id == context.tenant_id,
            User.username == user_data.username
        )
        existing_user = db.execute(stmt).scalar_one_or_none()
        
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Username '{user_data.username}' already exists"
            )
        
        # Check if email already exists in tenant
        stmt = select(User).where(
            User.tenant_id == context.tenant_id,
            User.email == user_data.email
        )
        existing_email = db.execute(stmt).scalar_one_or_none()
        
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{user_data.email}' already exists"
            )
        
        # Create new user
        new_user = User(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(context.tenant_id),
            username=user_data.username,
            email=user_data.email,
            hashed_password=get_password_hash(user_data.password),
            role=user_data.role,
            area=user_data.area,
            created_at=datetime.utcnow()
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        print(f"{timestamp} [USER MANAGEMENT] User created successfully: {new_user.id}")
        
        return UserResponse(
            id=str(new_user.id),
            username=new_user.username,
            email=new_user.email,
            role=new_user.role,
            area=new_user.area or "N/A",
            tenant_id=str(new_user.tenant_id),
            created_at=new_user.created_at.isoformat() if new_user.created_at else ""
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        print(f"{timestamp} [ERROR] Failed to create user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Delete a user (MASTER/ADMIN only)
    """
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    context = require_master_or_admin(request)
    
    print(f"{timestamp} [USER MANAGEMENT] Deleting user: {user_id}")
    
    try:
        # Find user
        stmt = select(User).where(
            User.id == uuid.UUID(user_id),
            User.tenant_id == context.tenant_id
        )
        user = db.execute(stmt).scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Prevent deleting yourself
        if str(user.id) == context.user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete your own account"
            )
        
        db.delete(user)
        db.commit()
        
        print(f"{timestamp} [USER MANAGEMENT] User deleted successfully: {user_id}")
        
        return {"success": True, "message": "User deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        print(f"{timestamp} [ERROR] Failed to delete user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )
