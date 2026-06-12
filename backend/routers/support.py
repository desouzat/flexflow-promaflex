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
import mimetypes
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

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

def send_ticket_email(
    ticket_id: str,
    username: str,
    email: str,
    description: str,
    support_email: str,
    attachment_name: str | None = None,
    attachment_path: str | None = None,
) -> bool:
    """
    Sends an email notification to the address defined in settings or SUPPORT_EMAIL_DESTINATION.

    Environment variables:
        SMTP_HOST         SMTP server hostname (default: smtp.gmail.com)
        SMTP_PORT         SMTP server port — 587 = STARTTLS, 465 = SSL (default: 587)
        SMTP_USER         SMTP login username (e.g. noreply@botcase.com.br)
        SMTP_PASS         SMTP login password or app-password
        SMTP_SENDER       Display sender address (falls back to SMTP_USER if not set)
        SMTP_SIMULATE     If set to "true" / "1" / "yes", skips real SMTP and logs only (default: false)

    Args:
        attachment_name:  Original filename displayed in the email body and as the MIME attachment name.
        attachment_path:  GCS public URL (https://storage.googleapis.com/...) or local filesystem path
                          to the file bytes to attach. If None or unreachable, the email is still sent
                          without an attachment (fallback, never crashes).

    Returns True if the email was delivered (or simulated), False on delivery failure.
    Falls back gracefully — never raises, never crashes the calling request thread.
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

    # ── Always print a console trace for traceability ────────────────────────
    print(f"\n{'='*80}")
    print("[SUPORTE] SUPPORT TICKET EMAIL DISPATCH")
    print(f"To: {support_email}")
    print(f"Subject: {subject}")
    print(body)
    print(f"{'='*80}\n")

    # ── Read SMTP configuration from environment ──────────────────────────────
    smtp_host     = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port_str = os.getenv("SMTP_PORT", "587")
    smtp_user     = os.getenv("SMTP_USER", "")
    smtp_pass     = os.getenv("SMTP_PASS", "")
    smtp_sender   = os.getenv("SMTP_SENDER", smtp_user)   # Falls back to SMTP_USER if not set
    simulate_raw  = os.getenv("SMTP_SIMULATE", "false").strip().lower()
    smtp_simulate = simulate_raw in ("true", "1", "yes")

    # ── Simulate mode (explicit mock) ─────────────────────────────────────────
    if smtp_simulate:
        print(f"[SMTP] SIMULATE mode active — skipping real SMTP dispatch for ticket {ticket_id}.")
        return True

    # ── Credentials gate ─────────────────────────────────────────────────────
    if not smtp_user or not smtp_pass:
        print(
            "[SMTP] SMTP_USER or SMTP_PASS not configured in environment. "
            "Ticket saved successfully; email not sent (no credentials). "
            "Set SMTP_SIMULATE=true to suppress this warning in test environments."
        )
        return False

    # ── Build the MIME message ────────────────────────────────────────────────
    try:
        smtp_port = int(smtp_port_str)
    except ValueError:
        print(f"[SMTP] Invalid SMTP_PORT value '{smtp_port_str}' — defaulting to 587.")
        smtp_port = 587

    msg = MIMEMultipart()
    msg['From']    = smtp_sender
    msg['To']      = support_email
    msg['Subject'] = subject
    msg['Reply-To'] = email  # Route replies to the ticket creator
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    # ── Physical file attachment (if provided) ────────────────────────────────
    # Downloads the file bytes from a GCS URL or reads from a local path,
    # then encodes them as a Base64 MIME attachment.
    # Failures here are non-fatal: the email is sent without the attachment
    # rather than blocking the entire notification dispatch.
    if attachment_path and attachment_name:
        try:
            file_bytes: bytes | None = None

            if attachment_path.startswith("http://") or attachment_path.startswith("https://"):
                # GCS public URL — fetch with a 15-second timeout
                resp = requests.get(attachment_path, timeout=15)
                resp.raise_for_status()
                file_bytes = resp.content
                print(f"[SMTP] Downloaded attachment from GCS ({len(file_bytes)} bytes): {attachment_path}")
            else:
                # Local filesystem path
                with open(attachment_path, "rb") as fh:
                    file_bytes = fh.read()
                print(f"[SMTP] Read attachment from local path ({len(file_bytes)} bytes): {attachment_path}")

            if file_bytes:
                # Detect MIME type from filename extension; fall back to octet-stream
                mime_type, _ = mimetypes.guess_type(attachment_name)
                if mime_type and "/" in mime_type:
                    main_type, sub_type = mime_type.split("/", 1)
                else:
                    main_type, sub_type = "application", "octet-stream"

                part = MIMEBase(main_type, sub_type)
                part.set_payload(file_bytes)
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=attachment_name,
                )
                msg.attach(part)
                print(f"[SMTP] Attachment encoded and added to email: '{attachment_name}' ({main_type}/{sub_type})")

        except Exception as attach_err:
            # Non-fatal: log and continue — email is still sent without attachment
            print(
                f"[SMTP] WARNING: Could not attach file '{attachment_name}': "
                f"{type(attach_err).__name__}: {attach_err}. "
                "Sending email without attachment."
            )

    # ── Establish secure SMTP connection with timeout guard ──────────────────
    # timeout=10 ensures the blocking connect()/starttls()/login() calls
    # fail fast on unreachable servers, preventing Gunicorn worker timeouts.
    server = None
    try:
        if smtp_port == 465:
            # SSL mode: full TLS tunnel from the first byte
            print(f"[SMTP] Connecting via SSL on {smtp_host}:{smtp_port} (timeout=10s)...")
            server = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            # STARTTLS mode (port 587 or custom): upgrade plain connection to TLS
            print(f"[SMTP] Connecting via STARTTLS on {smtp_host}:{smtp_port} (timeout=10s)...")
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()   # Re-identify after STARTTLS upgrade

        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_sender, [support_email], msg.as_string())
        print(f"✅ [SMTP] Email sent successfully → {support_email} via {smtp_host}:{smtp_port}")
        return True

    except smtplib.SMTPAuthenticationError as auth_err:
        print(
            f"❌ [SMTP] Authentication failed for user '{smtp_user}'. "
            f"Check SMTP_USER / SMTP_PASS credentials. Detail: {auth_err}"
        )
    except smtplib.SMTPConnectError as conn_err:
        print(
            f"❌ [SMTP] Could not connect to {smtp_host}:{smtp_port}. "
            f"Server may be unreachable or blocked by firewall. Detail: {conn_err}"
        )
    except smtplib.SMTPRecipientsRefused as ref_err:
        print(
            f"❌ [SMTP] Recipient '{support_email}' was refused by the server. Detail: {ref_err}"
        )
    except TimeoutError:
        print(
            f"❌ [SMTP] Connection to {smtp_host}:{smtp_port} timed out after 10s. "
            "Ticket is saved; email delivery skipped."
        )
    except Exception as e:
        print(f"❌ [SMTP] Unexpected error during email dispatch: {type(e).__name__}: {e}")
    finally:
        # Always attempt a clean QUIT to release the server-side connection slot
        if server is not None:
            try:
                server.quit()
            except Exception:
                pass  # If quit fails, the OS will close the socket on garbage collection

    print("[SMTP] Ticket saved successfully despite email failure. Console logs preserve ticket details.")
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
        from backend.services.gcs_service import GCSService
        gcs_service = GCSService()
        # Save file securely to GCS using ticket_id as the folder/identifier
        saved_path, attachment_filename = await gcs_service.upload_file(attachment, ticket_id)
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
        attachment_name=attachment_filename,
        attachment_path=attachment_path,
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
