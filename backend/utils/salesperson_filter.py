import uuid
from typing import Optional, List
from sqlalchemy.orm import Session
from backend.models import User, PurchaseOrder


def get_salesperson_filter_name(current_user: any, db: Session) -> Optional[str]:
    """
    Check if current_user is an Operador under COMERCIAL area.
    If yes, return db_user.name for salesperson isolation.
    If MASTER, ADMIN, or non-COMERCIAL, return None (bypass filter).
    """
    if not current_user or not getattr(current_user, 'id', None):
        return None

    role = (getattr(current_user, 'role', '') or '').lower()
    if role in ['admin', 'master']:
        return None

    try:
        user_uuid = uuid.UUID(str(current_user.id))
        db_user = db.query(User).filter(User.id == user_uuid).first()
        if db_user:
            u_role = (db_user.role or '').lower()
            u_area = (db_user.area or '').upper()
            if u_role == 'operador' and u_area == 'COMERCIAL':
                return db_user.name
    except Exception:
        pass

    return None


def po_matches_salesperson(po: PurchaseOrder, salesperson_name: Optional[str]) -> bool:
    """
    Returns True if salesperson_name is None (no filter) or if any item in the PO
    has extra_metadata["salesperson"] matching salesperson_name (case-insensitive).
    """
    if not salesperson_name:
        return True

    target = salesperson_name.strip().lower()
    for item in (po.items or []):
        meta = item.extra_metadata or {}
        sp = str(meta.get("salesperson") or "").strip().lower()
        if sp == target:
            return True

    return False


def filter_pos_by_salesperson(pos: List[PurchaseOrder], salesperson_name: Optional[str]) -> List[PurchaseOrder]:
    """
    Filter list of PurchaseOrder models by salesperson_name (if provided).
    """
    if not salesperson_name:
        return pos

    return [po for po in pos if po_matches_salesperson(po, salesperson_name)]
