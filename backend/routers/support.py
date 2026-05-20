"""
FlexFlow - Support Tickets Router
Handles user support ticket creation and management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid
from datetime import datetime

from backend.database import get_db
from backend.models import SupportTicket, User
from backend.routers.auth import get_current_user
from backend.schemas.auth_schema import UserInfo
from pydantic import BaseModel, Field

# ============================================================================
# SCHEMAS
# ============================================================================

class SupportTicketCreate(BaseModel):
    """Schema for creating a support ticket"""
    description: str = Field(..., min_length=10, max_length=5000, description="Problem description")

class SupportTicketResponse(BaseModel):
    """Schema for support ticket response"""
    id: uuid.UUID
    user_id: uuid.UUID
    description: str
    status: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    
    class Config:
        from_attributes = True

# ============================================================================
# ROUTER
# ============================================================================

router = APIRouter(prefix="/api/support", tags=["Support"])

@router.post("/report", response_model=SupportTicketResponse, status_code=status.HTTP_201_CREATED)
async def report_problem(
    ticket_data: SupportTicketCreate,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Report a problem by creating a support ticket.
    
    The ticket is saved to the database and details are printed to the terminal
    (simulating email notification to support team).
    
    Args:
        ticket_data: Support ticket creation data
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Created support ticket with ID for tracking
    """
    # Create support ticket
    new_ticket = SupportTicket(
        user_id=current_user.user_id,
        description=ticket_data.description,
        status="OPEN"
    )
    
    db.add(new_ticket)
    db.commit()
    db.refresh(new_ticket)
    
    # Print to terminal (Email Mock)
    print("\n" + "=" * 80)
    print("📧 NEW SUPPORT TICKET - EMAIL NOTIFICATION (MOCK)")
    print("=" * 80)
    print(f"Ticket ID: {new_ticket.id}")
    print(f"User: {current_user.username} ({current_user.email})")
    print(f"User Role: {current_user.role}")
    print(f"User Area: {current_user.area}")
    print(f"Status: {new_ticket.status}")
    print(f"Created At: {new_ticket.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 80)
    print("PROBLEM DESCRIPTION:")
    print(ticket_data.description)
    print("=" * 80)
    print(f"✅ Ticket saved to database and support team notified!\n")
    
    return new_ticket

@router.get("/tickets", response_model=List[SupportTicketResponse])
async def list_tickets(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List support tickets.
    
    Regular users see only their own tickets.
    Admin and Master users see all tickets.
    
    Args:
        current_user: Authenticated user
        db: Database session
        
    Returns:
        List of support tickets
    """
    if current_user.role in ["admin", "master"]:
        # Admin and Master can see all tickets
        tickets = db.query(SupportTicket).order_by(SupportTicket.created_at.desc()).all()
    else:
        # Regular users see only their own tickets
        tickets = db.query(SupportTicket).filter(
            SupportTicket.user_id == current_user.user_id
        ).order_by(SupportTicket.created_at.desc()).all()
    
    return tickets

@router.get("/tickets/{ticket_id}", response_model=SupportTicketResponse)
async def get_ticket(
    ticket_id: uuid.UUID,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific support ticket by ID.
    
    Args:
        ticket_id: Ticket UUID
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Support ticket details
    """
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )
    
    # Check permissions
    if current_user.role not in ["admin", "master"] and ticket.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this ticket"
        )
    
    return ticket
