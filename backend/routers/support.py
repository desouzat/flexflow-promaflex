"""
FlexFlow - Support Tickets Router
Handles user support ticket creation and management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from typing import List, Optional
import uuid
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from backend.database import get_db
from backend.models import SupportTicket, User, GlobalConfig
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
    ticket_id: str
    user_id: uuid.UUID
    description: str
    attachment_path: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    
    class Config:
        from_attributes = True

# ============================================================================
# HELPERS
# ============================================================================

def generate_ticket_id(db: Session) -> str:
    """
    Generates a unique sequential ticket ID in the format FF-YYYY-000X
    """
    current_year = datetime.now().year
    prefix = f"FF-{current_year}-"
    
    # Query count of tickets for this year to establish a sequence
    count = db.query(SupportTicket).filter(
        SupportTicket.ticket_id.like(f"{prefix}%")
    ).count()
    
    seq = count + 1
    # Loop to prevent collisions (e.g. if tickets are deleted)
    while True:
        ticket_id = f"{prefix}{seq:04d}"
        exists = db.query(SupportTicket).filter(SupportTicket.ticket_id == ticket_id).first()
        if not exists:
            break
        seq += 1
        
    return ticket_id

def send_ticket_email(ticket_id: str, username: str, email: str, description: str, support_email: str, attachment_name: str | None = None) -> bool:
    """
    Sends an email notification to the address defined in settings or SUPPORT_EMAIL_DESTINATION.
    Falls back to console logging if credentials or mail server are not configured.
    """
    if not support_email:
        print("[WARNING] Support email destination is not defined. Falling back to console logging.")
        return False

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    subject = f"{ticket_id} - FlexFlow Issue {timestamp}"
    
    body = f"""
[SUPORTE] NOVO TICKET DE SUPORTE DETECTADO
----------------------------------------
Ticket ID: {ticket_id}
Data/Hora: {timestamp}
Usuário: {username} ({email})
----------------------------------------
DESCRIÇÃO DO PROBLEMA:
{description}
----------------------------------------
Anexo: {attachment_name or "Nenhum"}
"""

    # Traceability simulated email message requested
    print(f"\n--- SIMULATED EMAIL SENT TO: {support_email} | TICKET: {ticket_id} ---")

    print("\n" + "=" * 80)
    print("[SUPORTE] SENDING SUPPORT TICKET EMAIL (COMPLETE BODY BELOW)...")
    print(f"To: {support_email}")
    print(f"Subject: {subject}")
    print(body)
    print("=" * 80 + "\n")

    # Read SMTP credentials
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port_str = os.getenv("SMTP_PORT", "587")
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")

    if not smtp_user or not smtp_pass:
        print("[INFO] SMTP credentials not fully configured in env (SMTP_USER/SMTP_PASS). Treating console log as successful mock delivery.")
        return True

    try:
        smtp_port = int(smtp_port_str)
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = support_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # Connect to SMTP server
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, support_email, msg.as_string())
        server.close()
        print(f"✅ Email sent successfully to {support_email} via {smtp_host}:{smtp_port}")
        return True
    except Exception as e:
        print(f"❌ Error sending real SMTP email: {e}")
        print("[FALLBACK] Saved ticket successfully despite email failure. Console logs preserve ticket details.")
        return False

# ============================================================================
# ROUTER
# ============================================================================

router = APIRouter(prefix="/api/support", tags=["Support"])

@router.post("/ticket", response_model=SupportTicketResponse, status_code=status.HTTP_201_CREATED)
async def create_support_ticket(
    description: str = Form(...),
    attachment: Optional[UploadFile] = File(None),
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a support ticket, upload optional attachment, generate ticket ID,
    send email notification (with fallback), and save to database.
    """
    # 1. Generate unique sequential ticket ID
    ticket_id = generate_ticket_id(db)
    
    # 2. Process attachment if present
    attachment_path = None
    attachment_filename = None
    if attachment:
        from backend.services.file_service import FileService
        file_service = FileService()
        # Save file securely
        saved_path, attachment_filename = await file_service.save_file(attachment, current_user.tenant_id)
        attachment_path = saved_path

    # 3. Create ticket model using the dictionary reassignment technique
    # Note: user_id needs to be resolved as UUID
    new_ticket = SupportTicket(
        user_id=uuid.UUID(str(current_user.id)),
        ticket_id=ticket_id,
        description=description,
        status="OPEN"
    )
    
    # Dictionary reassignment technique
    ticket_data_dict = {"attachment_path": attachment_path}
    new_ticket.attachment_path = ticket_data_dict["attachment_path"]

    db.add(new_ticket)
    db.commit()

    # Guarantee writing via flag_modified
    flag_modified(new_ticket, 'attachment_path')
    db.commit()
    db.refresh(new_ticket)

    # 4. Email integration (non-blocking / won't crash if it fails)
    # Get support email from database setting (tenant-isolated)
    tenant_uuid = uuid.UUID(str(current_user.tenant_id))
    config = db.query(GlobalConfig).filter(
        GlobalConfig.tenant_id == tenant_uuid,
        GlobalConfig.config_key == "support_email"
    ).first()
    
    support_email = config.config_value if config else os.getenv("SUPPORT_EMAIL_DESTINATION", "suporte@flexflow.com.br")

    # Get current user details from db to get their name
    user_record = db.query(User).filter(User.id == uuid.UUID(str(current_user.id))).first()
    email_addr = current_user.email
    user_name = user_record.name if user_record else current_user.name
    
    send_ticket_email(
        ticket_id=ticket_id,
        username=user_name,
        email=email_addr,
        description=description,
        support_email=support_email,
        attachment_name=attachment_filename
    )

    return new_ticket

@router.post("/report", response_model=SupportTicketResponse, status_code=status.HTTP_201_CREATED)
async def report_problem(
    ticket_data: SupportTicketCreate,
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Legacy endpoint redirecting to new ticket logic for backwards compatibility.
    """
    return await create_support_ticket(
        description=ticket_data.description,
        attachment=None,
        current_user=current_user,
        db=db
    )

@router.get("/tickets", response_model=List[SupportTicketResponse])
async def list_tickets(
    current_user: UserInfo = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List support tickets.
    """
    if current_user.role.lower() in ["admin", "master"]:
        # Admin and Master can see all tickets
        tickets = db.query(SupportTicket).order_by(SupportTicket.created_at.desc()).all()
    else:
        # Regular users see only their own tickets
        tickets = db.query(SupportTicket).filter(
            SupportTicket.user_id == uuid.UUID(str(current_user.id))
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
    """
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found"
        )
    
    # Check permissions
    if current_user.role.lower() not in ["admin", "master"] and ticket.user_id != uuid.UUID(str(current_user.id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view this ticket"
        )
    
    return ticket
