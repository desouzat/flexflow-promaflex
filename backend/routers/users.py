"""
User Management Router
RBAC-restricted endpoints for managing users (ADMIN only)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr
import uuid

from backend.database import get_db
from backend.models import User
from backend.routers.auth import get_password_hash, SECURITY_PEPPER, get_current_user
from backend.schemas.auth_schema import UserInfo

print("[DEBUG] Pepper loaded in users router:", bool(SECURITY_PEPPER))

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


class UserUpdate(BaseModel):
    """Schema for updating an existing user"""
    role: str
    area: str
    password: Optional[str] = None
    # FF-HARDENING-011: SLA manager delegation flag (only meaningful for 'master' role)
    is_sla_manager: Optional[bool] = None


class UserResponse(BaseModel):
    """Schema for user response"""
    id: str
    username: str
    email: str
    role: str
    area: str
    tenant_id: str
    created_at: str
    is_sla_manager: bool = False  # FF-HARDENING-011

    class Config:
        from_attributes = True


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.get("", response_model=List[UserResponse])
@router.get("/", response_model=List[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    List all users in the tenant (ADMIN only)
    """
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    
    # SECURITY AUDIT: Strictly raise HTTP_403_FORBIDDEN on role mismatch
    if current_user.role.lower() != 'admin':
        print(f"{timestamp} [RBAC] Access denied: user {current_user.id} (role: {current_user.role}) attempted to access user management")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only ADMIN users can manage users."
        )
    
    print(f"{timestamp} [USER MANAGEMENT] Listing users for tenant: {current_user.tenant_id}")
    
    try:
        # Query users in the same tenant (casted as UUID for strict PostgreSQL mapping)
        stmt = select(User).where(User.tenant_id == uuid.UUID(current_user.tenant_id)).order_by(User.created_at.desc())
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
                created_at=user.created_at.isoformat() if user.created_at else "",
                is_sla_manager=bool(getattr(user, 'is_sla_manager', False)),  # FF-HARDENING-011
            ))
        
        return user_list
        
    except Exception as e:
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        print(f"{timestamp} [ERROR] Failed to list users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list users: {str(e)}"
        )


@router.post("", response_model=UserResponse)
@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Create a new user (ADMIN only)
    """
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    
    # SECURITY AUDIT: Strictly raise HTTP_403_FORBIDDEN on role mismatch
    if current_user.role.lower() != 'admin':
        print(f"{timestamp} [RBAC] Access denied: user {current_user.id} (role: {current_user.role}) attempted to access user management")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only ADMIN users can manage users."
        )
    
    print(f"{timestamp} [USER MANAGEMENT] Creating user: {user_data.username} (role: {user_data.role})")
    
    try:
        # Validate role
        valid_roles = ['master', 'admin', 'operator', 'user']
        if user_data.role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
            )
        
        # Check if username already exists in tenant
        stmt = select(User).where(
            User.tenant_id == uuid.UUID(current_user.tenant_id),
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
            User.tenant_id == uuid.UUID(current_user.tenant_id),
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
            tenant_id=uuid.UUID(current_user.tenant_id),
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
            created_at=new_user.created_at.isoformat() if new_user.created_at else "",
            is_sla_manager=bool(getattr(new_user, 'is_sla_manager', False)),  # FF-HARDENING-011
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
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Delete a user (ADMIN only)
    """
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    
    # SECURITY AUDIT: Strictly raise HTTP_403_FORBIDDEN on role mismatch
    if current_user.role.lower() != 'admin':
        print(f"{timestamp} [RBAC] Access denied: user {current_user.id} (role: {current_user.role}) attempted to access user management")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only ADMIN users can manage users."
        )
    
    print(f"{timestamp} [USER MANAGEMENT] Deleting user: {user_id}")
    
    try:
        # Find user
        stmt = select(User).where(
            User.id == uuid.UUID(user_id),
            User.tenant_id == uuid.UUID(current_user.tenant_id)
        )
        user = db.execute(stmt).scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Prevent deleting yourself
        if str(user.id) == current_user.id:
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


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: UserInfo = Depends(get_current_user)
):
    """
    Update user's Role and Area (ADMIN only)
    """
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    
    # SECURITY AUDIT: Strictly raise HTTP_403_FORBIDDEN on role mismatch
    if current_user.role.lower() != 'admin':
        print(f"{timestamp} [RBAC] Access denied: user {current_user.id} (role: {current_user.role}) attempted to access user management")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only ADMIN users can manage users."
        )
    
    print(f"{timestamp} [USER MANAGEMENT] Updating user {user_id}: role={user_data.role}, area={user_data.area}")
    
    try:
        # Validate role
        valid_roles = ['master', 'admin', 'operator', 'user']
        if user_data.role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Must be one of: {', '.join(valid_roles)}"
            )
            
        # Find user
        stmt = select(User).where(
            User.id == uuid.UUID(user_id),
            User.tenant_id == uuid.UUID(current_user.tenant_id)
        )
        user = db.execute(stmt).scalar_one_or_none()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
            
        # Update fields
        user.role = user_data.role
        user.area = user_data.area
        if user_data.password:
            user.hashed_password = get_password_hash(user_data.password)
        # FF-HARDENING-011: is_sla_manager can only be set for master role users
        if user_data.is_sla_manager is not None:
            if user_data.role == 'master':
                user.is_sla_manager = user_data.is_sla_manager
            else:
                # Silently reset if role is not master (safety guard)
                user.is_sla_manager = False
        user.updated_at = datetime.utcnow()
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        print(f"{timestamp} [USER MANAGEMENT] User updated successfully: {user.id}")
        
        return UserResponse(
            id=str(user.id),
            username=user.username,
            email=user.email,
            role=user.role,
            area=user.area or "N/A",
            tenant_id=str(user.tenant_id),
            created_at=user.created_at.isoformat() if user.created_at else "",
            is_sla_manager=bool(getattr(user, 'is_sla_manager', False)),  # FF-HARDENING-011
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        print(f"{timestamp} [ERROR] Failed to update user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )
