"""
FlexFlow - Settings Router
Handles system settings parameters configuration (Admin only, tenant-isolated).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid
import os
from pydantic import BaseModel, EmailStr
from typing import Optional

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


# ============================================================
# FF-HARDENING-010: SLA Parameter Configuration Endpoints
# ============================================================

# Default values for SLA parameters
SLA_CONFIG_DEFAULTS = {
    "sla_total_hours":  {"value": "240", "type": "int",    "description": "SLA total máximo em horas para o fluxo completo do pedido"},
    "sla_area_hours":   {"value": "24",  "type": "int",    "description": "SLA por setor/área operacional em horas"},
    "sla_start_hour":   {"value": "8",   "type": "int",    "description": "Hora de início do expediente (0-23)"},
    "sla_end_hour":     {"value": "18",  "type": "int",    "description": "Hora de encerramento do expediente (0-23)"},
    "sla_working_days": {"value": "Mon-Fri", "type": "str", "description": "Dias úteis de trabalho (ex: Mon-Fri, Mon-Sat)"},
}


class SlaConfigResponse(BaseModel):
    """Response schema for SLA configuration"""
    sla_total_hours: int = 240
    sla_area_hours: int = 24
    sla_start_hour: int = 8
    sla_end_hour: int = 18
    sla_working_days: str = "Mon-Fri"
    sla_manager_email: Optional[str] = None  # FF-HARDENING-011


class SlaConfigUpdate(BaseModel):
    """Update schema for SLA configuration (all fields optional)"""
    sla_total_hours: Optional[int] = None
    sla_area_hours: Optional[int] = None
    sla_start_hour: Optional[int] = None
    sla_end_hour: Optional[int] = None
    sla_working_days: Optional[str] = None
    sla_manager_email: Optional[str] = None  # FF-HARDENING-011


def _is_privileged(role: str) -> bool:
    """Returns True if the role has admin-level settings access."""
    return role.lower() in ("admin", "master")


@router.get("/sla-config", response_model=SlaConfigResponse)
async def get_sla_config(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    FF-HARDENING-010: Get current SLA parameters.
    Returns defaults for any keys not yet persisted to GlobalConfig.
    Accessible by admin and master roles.
    """
    if not _is_privileged(current_user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Apenas administradores e masters podem visualizar os parâmetros de SLA.",
        )

    tenant_uuid = uuid.UUID(str(current_user.tenant_id))
    sla_keys = list(SLA_CONFIG_DEFAULTS.keys()) + ["sla_manager_email"]

    rows = db.query(GlobalConfig).filter(
        GlobalConfig.tenant_id == tenant_uuid,
        GlobalConfig.config_key.in_(sla_keys),
    ).all()

    result = {k: v["value"] for k, v in SLA_CONFIG_DEFAULTS.items()}
    result["sla_manager_email"] = None  # FF-HARDENING-011
    for row in rows:
        result[row.config_key] = row.config_value

    return SlaConfigResponse(
        sla_total_hours=int(result["sla_total_hours"]),
        sla_area_hours=int(result["sla_area_hours"]),
        sla_start_hour=int(result["sla_start_hour"]),
        sla_end_hour=int(result["sla_end_hour"]),
        sla_working_days=str(result["sla_working_days"]),
        sla_manager_email=result.get("sla_manager_email"),  # FF-HARDENING-011
    )


@router.put("/sla-config", response_model=SlaConfigResponse)
async def update_sla_config(
    payload: SlaConfigUpdate,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    FF-HARDENING-010: Upsert SLA parameters.
    Only sends the provided (non-None) fields. Missing fields retain their current value.
    Accessible by admin and master roles.
    """
    if not _is_privileged(current_user.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Apenas administradores e masters podem alterar os parâmetros de SLA.",
        )

    tenant_uuid = uuid.UUID(str(current_user.tenant_id))
    user_uuid = uuid.UUID(str(current_user.id))

    # Build dict of updates to apply (only non-None fields)
    updates: dict = {}
    if payload.sla_total_hours is not None:
        updates["sla_total_hours"] = str(payload.sla_total_hours)
    if payload.sla_area_hours is not None:
        updates["sla_area_hours"] = str(payload.sla_area_hours)
    if payload.sla_start_hour is not None:
        if not (0 <= payload.sla_start_hour <= 23):
            raise HTTPException(status_code=400, detail="sla_start_hour deve estar entre 0 e 23.")
        updates["sla_start_hour"] = str(payload.sla_start_hour)
    if payload.sla_end_hour is not None:
        if not (1 <= payload.sla_end_hour <= 24):
            raise HTTPException(status_code=400, detail="sla_end_hour deve estar entre 1 e 24.")
        updates["sla_end_hour"] = str(payload.sla_end_hour)
    if payload.sla_working_days is not None:
        if not payload.sla_working_days.strip():
            raise HTTPException(status_code=400, detail="sla_working_days não pode ser vazio.")
        updates["sla_working_days"] = payload.sla_working_days.strip()
    # FF-HARDENING-011: handle sla_manager_email separately (no SLA_CONFIG_DEFAULTS entry)
    if payload.sla_manager_email is not None:
        mgr_row = db.query(GlobalConfig).filter(
            GlobalConfig.tenant_id == tenant_uuid,
            GlobalConfig.config_key == "sla_manager_email",
        ).first()
        new_mgr_email = payload.sla_manager_email.strip() or None
        if new_mgr_email is None and mgr_row:
            db.delete(mgr_row)
        elif new_mgr_email:
            if mgr_row:
                mgr_row.config_value = new_mgr_email
                mgr_row.updated_by = user_uuid
            else:
                db.add(GlobalConfig(
                    id=uuid.uuid4(),
                    tenant_id=tenant_uuid,
                    config_key="sla_manager_email",
                    config_value=new_mgr_email,
                    config_type="str",
                    description="E-mail do responsável pelo SLA (delegação)",
                    updated_by=user_uuid,
                ))

    # Validate start < end if both provided
    start = int(updates.get("sla_start_hour", -1)) if "sla_start_hour" in updates else None
    end   = int(updates.get("sla_end_hour",   -1)) if "sla_end_hour"   in updates else None
    if start is not None and end is not None and start >= end:
        raise HTTPException(status_code=400, detail="sla_start_hour deve ser menor que sla_end_hour.")

    # Upsert each key
    for key, new_value in updates.items():
        meta = SLA_CONFIG_DEFAULTS[key]
        existing = db.query(GlobalConfig).filter(
            GlobalConfig.tenant_id == tenant_uuid,
            GlobalConfig.config_key == key,
        ).first()

        if existing:
            existing.config_value = new_value
            existing.updated_by = user_uuid
        else:
            db.add(GlobalConfig(
                id=uuid.uuid4(),
                tenant_id=tenant_uuid,
                config_key=key,
                config_value=new_value,
                config_type=meta["type"],
                description=meta["description"],
                updated_by=user_uuid,
            ))

    db.commit()

    # Return fresh read
    rows = db.query(GlobalConfig).filter(
        GlobalConfig.tenant_id == tenant_uuid,
        GlobalConfig.config_key.in_(list(SLA_CONFIG_DEFAULTS.keys()) + ["sla_manager_email"]),
    ).all()

    result = {k: v["value"] for k, v in SLA_CONFIG_DEFAULTS.items()}
    result["sla_manager_email"] = None  # FF-HARDENING-011
    for row in rows:
        result[row.config_key] = row.config_value

    return SlaConfigResponse(
        sla_total_hours=int(result["sla_total_hours"]),
        sla_area_hours=int(result["sla_area_hours"]),
        sla_start_hour=int(result["sla_start_hour"]),
        sla_end_hour=int(result["sla_end_hour"]),
        sla_working_days=str(result["sla_working_days"]),
        sla_manager_email=result.get("sla_manager_email"),  # FF-HARDENING-011
    )


# ============================================================
# FF-HARDENING-011: SLA Manager Email Delegation Endpoints
# ============================================================

class SlaManagerEmailUpdate(BaseModel):
    """Schema for setting/clearing the SLA manager email"""
    sla_manager_email: Optional[str] = None


@router.get("/sla-access")
async def check_sla_access(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    FF-HARDENING-011: Any authenticated user may check if they have SLA config access.
    Grants access if admin/master OR if email matches sla_manager_email config.
    """
    tenant_uuid = uuid.UUID(str(current_user.tenant_id))
    mgr_config = db.query(GlobalConfig).filter(
        GlobalConfig.tenant_id == tenant_uuid,
        GlobalConfig.config_key == "sla_manager_email",
    ).first()
    sla_mgr_email = mgr_config.config_value.strip().lower() if mgr_config and mgr_config.config_value else None

    user_email = (current_user.email or "").strip().lower()
    is_privileged = _is_privileged(current_user.role)
    email_match = bool(sla_mgr_email and user_email and user_email == sla_mgr_email)

    return {
        "has_access": is_privileged or email_match,
        "sla_manager_email": mgr_config.config_value if mgr_config else None,
    }


@router.get("/sla-manager-email")
async def get_sla_manager_email_ep(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FF-HARDENING-011: Get the SLA manager email (admin only)."""
    if current_user.role.lower() != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem consultar o responsavel pelo SLA.")
    tenant_uuid = uuid.UUID(str(current_user.tenant_id))
    config = db.query(GlobalConfig).filter(
        GlobalConfig.tenant_id == tenant_uuid,
        GlobalConfig.config_key == "sla_manager_email",
    ).first()
    return {"sla_manager_email": config.config_value if config else None}


@router.put("/sla-manager-email")
async def update_sla_manager_email_ep(
    payload: SlaManagerEmailUpdate,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """FF-HARDENING-011: Set or clear the SLA manager email (admin only)."""
    if current_user.role.lower() != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas administradores podem configurar o responsavel pelo SLA.")
    tenant_uuid = uuid.UUID(str(current_user.tenant_id))
    user_uuid = uuid.UUID(str(current_user.id))
    new_email = (payload.sla_manager_email or "").strip() or None

    config = db.query(GlobalConfig).filter(
        GlobalConfig.tenant_id == tenant_uuid,
        GlobalConfig.config_key == "sla_manager_email",
    ).first()

    if new_email is None:
        if config:
            db.delete(config)
            db.commit()
        return {"sla_manager_email": None, "message": "Delegacao removida."}

    if config:
        config.config_value = new_email
    else:
        config = GlobalConfig(
            tenant_id=tenant_uuid,
            config_key="sla_manager_email",
            config_value=new_email,
            updated_by=user_uuid,
        )
        db.add(config)
    db.commit()
    return {"sla_manager_email": new_email, "message": "Email do responsavel pelo SLA atualizado."}

