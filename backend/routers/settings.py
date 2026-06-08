"""
FlexFlow - Settings Router
Handles system settings parameters configuration (Admin only, tenant-isolated).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid
import os
from pydantic import BaseModel, EmailStr

from backend.database import get_db
from backend.models import GlobalConfig
from backend.routers.auth import get_current_user
from backend.schemas.auth_schema import UserInfo

router = APIRouter(prefix="/api/settings", tags=["Settings"])

class SupportEmailUpdate(BaseModel):
    """Schema for updating support email"""
    support_email: EmailStr

@router.get("/support-email")
async def get_support_email(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the support email destination (Admin only)
    """
    if current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Apenas administradores podem visualizar as configurações."
        )
        
    tenant_uuid = uuid.UUID(str(current_user.tenant_id))
    config = db.query(GlobalConfig).filter(
        GlobalConfig.tenant_id == tenant_uuid,
        GlobalConfig.config_key == "support_email"
    ).first()
    
    email = config.config_value if config else os.getenv("SUPPORT_EMAIL_DESTINATION", "suporte@flexflow.com.br")
    return {"support_email": email}

@router.post("/support-email")
async def update_support_email(
    payload: SupportEmailUpdate,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update the support email destination (Admin only)
    """
    if current_user.role.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Apenas administradores podem alterar as configurações."
        )
        
    tenant_uuid = uuid.UUID(str(current_user.tenant_id))
    user_uuid = uuid.UUID(str(current_user.id))
    
    config = db.query(GlobalConfig).filter(
        GlobalConfig.tenant_id == tenant_uuid,
        GlobalConfig.config_key == "support_email"
    ).first()
    
    if config:
        config.config_value = payload.support_email
        config.updated_by = user_uuid
    else:
        config = GlobalConfig(
            id=uuid.uuid4(),
            tenant_id=tenant_uuid,
            config_key="support_email",
            config_value=payload.support_email,
            config_type="str",
            description="E-mail de destino para notificacoes de suporte",
            updated_by=user_uuid
        )
        db.add(config)
        
    db.commit()
    db.refresh(config)
    return {"support_email": config.config_value}
