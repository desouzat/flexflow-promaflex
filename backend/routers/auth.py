"""
FlexFlow Authentication Router
Endpoints for login and user authentication.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
import jwt
from passlib.context import CryptContext

from backend.schemas.auth_schema import LoginRequest, TokenResponse, MeResponse, UserInfo
from backend.database import get_db

# Security configuration
SECRET_KEY = "your-secret-key-here-change-in-production"  # TODO: Move to environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
security = HTTPBearer()

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return encoded_jwt


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> UserInfo:
    """
    Dependency to get current authenticated user from JWT token.
    This should be used in all protected endpoints.
    """
    token = credentials.credentials
    payload = decode_token(token)
    
    # Extract user info from token
    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    email = payload.get("email")
    
    if not user_id or not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # In production, you would fetch user from database here
    # For now, return user info from token
    user_info = UserInfo(
        id=user_id,
        tenant_id=tenant_id,
        email=email,
        name=payload.get("name", "User"),
        role=payload.get("role", "user"),
        permissions=payload.get("permissions", []),
        is_active=True
    )
    
    return user_info


@router.post("/login", response_model=TokenResponse)
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT token.
    
    **Note:** This is a mock implementation for the kickoff.
    In production, this should:
    1. Query the database for the user
    2. Verify the password hash
    3. Check if user is active
    4. Return proper error messages
    """
    
    # Mock authentication - REPLACE WITH REAL DATABASE QUERY
    # For demo purposes, accept any email/password combination
    
    # Simulate database user lookup
    mock_user = {
        "id": "user-123-456",
        "tenant_id": "tenant-abc-def",
        "email": login_data.email,
        "name": "Demo User",
        "role": "admin",
        "permissions": [
            "po.create",
            "po.read",
            "po.update",
            "po.approve_comercial",
            "po.approve_pcp",
            "po.approve_producao",
            "po.complete_expedicao",
            "po.complete_faturamento",
            "po.approve_despacho"
        ],
        "is_active": True,
        "hashed_password": get_password_hash("password123")  # Mock password
    }
    
    # In production, verify password:
    # if not verify_password(login_data.password, mock_user["hashed_password"]):
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Incorrect email or password"
    #     )
    
    # Create JWT token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": mock_user["id"],
            "tenant_id": mock_user["tenant_id"],
            "email": mock_user["email"],
            "name": mock_user["name"],
            "role": mock_user["role"],
            "permissions": mock_user["permissions"]
        },
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
    )


@router.get("/me", response_model=MeResponse)
async def get_current_user_info(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user information.
    
    This endpoint verifies the JWT token and returns user details.
    Use this to check if a token is still valid.
    """
    
    # In production, fetch additional user/tenant info from database
    # For now, return info from token
    
    return MeResponse(
        user=current_user,
        tenant_name="Demo Tenant",  # Would be fetched from database
        authenticated_at=datetime.utcnow()
    )


@router.post("/logout")
async def logout(current_user: UserInfo = Depends(get_current_user)):
    """
    Logout endpoint (for completeness).
    
    Since we're using stateless JWT tokens, logout is typically handled
    client-side by removing the token. In production, you might want to
    implement token blacklisting.
    """
    return {"message": "Successfully logged out"}
