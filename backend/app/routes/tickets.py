"""Support ticket endpoints with intentional access control vulnerabilities.

Provides ticket CRUD, messaging, and file attachment management for the
customer support system. Contains deliberate vulnerabilities:
  - Internal notes leak via forged JWT role (CWE-639)
  - Missing access check on ticket attachments (CWE-862)
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.middleware.auth_middleware import get_current_user
from app.models.ticket import Ticket, TicketAttachment, TicketMessage
from app.schemas.tickets import (
    AttachmentResponse,
    CreateMessageRequest,
    CreateTicketRequest,
    TicketMessageResponse,
    TicketResponse,
    TicketSummaryResponse,
)
from app.utils.image_handler import async_save_upload

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_message_response(msg: TicketMessage) -> TicketMessageResponse:
    """Build a TicketMessageResponse from an ORM TicketMessage.

    Args:
        msg: TicketMessage ORM instance with user relationship loaded.

    Returns:
        Pydantic response with username extracted from user relationship.
    """
    return TicketMessageResponse(
        id=msg.id,
        ticket_id=msg.ticket_id,
        user_id=msg.user_id,
        username=msg.user.username,
        body=msg.body,
        is_internal=msg.is_internal,
        created_at=msg.created_at,
    )


def _build_ticket_response(
    ticket: Ticket,
    messages: list[TicketMessageResponse],
) -> TicketResponse:
    """Build a TicketResponse from an ORM Ticket and pre-built messages.

    Args:
        ticket: Ticket ORM instance.
        messages: Already-built TicketMessageResponse list.

    Returns:
        Full ticket response with messages.
    """
    return TicketResponse(
        id=ticket.id,
        user_id=ticket.user_id,
        subject=ticket.subject,
        status=ticket.status,
        priority=ticket.priority,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        messages=messages,
    )


def _is_staff(role: str) -> bool:
    """Check if a role has support/admin privileges.

    Args:
        role: User role string from JWT claims.

    Returns:
        True if the role is support or admin.
    """
    return role in ("support", "admin")


# ---------------------------------------------------------------------------
# POST /api/tickets — Create ticket (secure)
# ---------------------------------------------------------------------------


@router.post(
    "",
    response_model=TicketResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_ticket(
    data: CreateTicketRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> TicketResponse:
    """Create a new support ticket with an initial message.

    Any authenticated user can create tickets. The first message
    body comes from the request payload.

    Args:
        data: Subject and body for the new ticket.
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Returns:
        The created ticket with its initial message.
    """
    ticket = Ticket(
        user_id=current_user["user_id"],
        subject=data.subject,
    )
    db.add(ticket)
    await db.flush()

    message = TicketMessage(
        ticket_id=ticket.id,
        user_id=current_user["user_id"],
        body=data.body,
        is_internal=False,
    )
    db.add(message)
    await db.commit()

    await db.refresh(message, attribute_names=["user"])

    return _build_ticket_response(
        ticket,
        [_build_message_response(message)],
    )


# ---------------------------------------------------------------------------
# GET /api/tickets — List tickets (secure)
# ---------------------------------------------------------------------------


@router.get("", response_model=list[TicketSummaryResponse])
async def list_tickets(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[TicketSummaryResponse]:
    """List support tickets visible to the authenticated user.

    Customers and sellers see only their own tickets. Support and
    admin roles see all tickets. Ordered by most recent first.

    Args:
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Returns:
        List of ticket summaries.
    """
    if _is_staff(current_user["role"]):
        result = await db.execute(
            select(Ticket).order_by(Ticket.created_at.desc())
        )
    else:
        result = await db.execute(
            select(Ticket)
            .where(Ticket.user_id == current_user["user_id"])
            .order_by(Ticket.created_at.desc())
        )

    tickets = result.scalars().all()
    return [
        TicketSummaryResponse(
            id=t.id,
            user_id=t.user_id,
            subject=t.subject,
            status=t.status,
            priority=t.priority,
            created_at=t.created_at,
        )
        for t in tickets
    ]


# ---------------------------------------------------------------------------
# GET /api/tickets/{ticket_id} — Ticket detail (VULN: Internal Notes Leak)
# ---------------------------------------------------------------------------


# VULN: Internal Notes Leak - Internal messages (is_internal=True) are shown
# when the JWT role is "support" or "admin". Since the role comes from the JWT
# payload (VULN 9) and the JWT secret is guessable (VULN 5), an attacker can
# forge a token with role=support to see internal staff notes containing
# sensitive information (refund amounts, VIP status, coupon configurations).
# Ref: https://hackerone.com/reports/895772
@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket_detail(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> TicketResponse:
    """Get full ticket detail with messages.

    Access control: ticket creator or support/admin can view.
    Internal notes (is_internal=True) are filtered out for non-staff
    users. However, since the role is read from the JWT (not DB),
    a forged JWT with role=support bypasses this filter.

    Args:
        ticket_id: ID of the ticket to retrieve.
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Returns:
        Full ticket with messages (internal notes filtered by role).

    Raises:
        HTTPException: 404 if not found, 403 if no access.
    """
    result = await db.execute(
        select(Ticket)
        .where(Ticket.id == ticket_id)
        .options(selectinload(Ticket.messages).selectinload(TicketMessage.user))
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    is_owner = ticket.user_id == current_user["user_id"]
    is_privileged = _is_staff(current_user["role"])

    if not is_owner and not is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own tickets",
        )

    # VULN: Role-based filtering uses JWT role (forged via VULN 5 + VULN 9)
    # An attacker with role=support sees internal notes meant only for staff
    messages: list[TicketMessageResponse] = []
    for msg in ticket.messages:
        if msg.is_internal and not is_privileged:
            continue
        messages.append(_build_message_response(msg))

    return _build_ticket_response(ticket, messages)


# ---------------------------------------------------------------------------
# POST /api/tickets/{ticket_id}/messages — Add message (secure)
# ---------------------------------------------------------------------------


@router.post(
    "/{ticket_id}/messages",
    response_model=TicketMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_message(
    ticket_id: int,
    data: CreateMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> TicketMessageResponse:
    """Add a message to an existing ticket.

    Access control: ticket creator or support/admin can post.
    The is_internal flag is silently ignored for non-staff users
    to prevent customers from creating internal notes.

    Args:
        ticket_id: ID of the ticket to add a message to.
        data: Message body and optional is_internal flag.
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Returns:
        The created message.

    Raises:
        HTTPException: 404 if ticket not found, 403 if no access.
    """
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    is_owner = ticket.user_id == current_user["user_id"]
    is_privileged = _is_staff(current_user["role"])

    if not is_owner and not is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this ticket",
        )

    # Silently ignore is_internal for non-staff users
    is_internal = data.is_internal if is_privileged else False

    message = TicketMessage(
        ticket_id=ticket.id,
        user_id=current_user["user_id"],
        body=data.body,
        is_internal=is_internal,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message, attribute_names=["user"])

    return _build_message_response(message)


# ---------------------------------------------------------------------------
# GET /api/tickets/{ticket_id}/attachments — List attachments (VULN: Missing Access Check)
# ---------------------------------------------------------------------------


# VULN: Missing Access Check - Only verifies authentication, NOT that the
# user has access to the specified ticket. Any authenticated user can list
# attachments of any ticket by enumerating ticket_id values.
# Attachments may contain sensitive files (photos of documents, receipts, etc.)
# Ref: https://hackerone.com/reports/314808
@router.get(
    "/{ticket_id}/attachments",
    response_model=list[AttachmentResponse],
)
async def list_attachments(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> list[AttachmentResponse]:
    """List all file attachments for a ticket — no ownership check.

    Only verifies that the caller is authenticated. Does NOT verify
    that the caller owns the ticket or has support/admin role.
    Attachments are served via /static/ and may contain PII.

    Args:
        ticket_id: ID of the ticket whose attachments to list.
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Returns:
        List of attachment metadata (includes filepath for download).
    """
    result = await db.execute(
        select(TicketAttachment)
        .where(TicketAttachment.ticket_id == ticket_id)
        .order_by(TicketAttachment.uploaded_at)
    )
    attachments = result.scalars().all()

    return [
        AttachmentResponse(
            id=a.id,
            ticket_id=a.ticket_id,
            filename=a.filename,
            filepath=a.filepath,
            content_type=a.content_type,
            file_size=a.file_size,
            uploaded_at=a.uploaded_at,
        )
        for a in attachments
    ]


# ---------------------------------------------------------------------------
# POST /api/tickets/{ticket_id}/attachments — Upload attachment (secure)
# ---------------------------------------------------------------------------


@router.post(
    "/{ticket_id}/attachments",
    response_model=AttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    ticket_id: int,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> AttachmentResponse:
    """Upload a file attachment to a ticket.

    Access control: ticket creator or support/admin can upload.
    Uses the shared async_save_upload utility from image_handler.

    Args:
        ticket_id: ID of the ticket to attach the file to.
        file: The uploaded file.
        db: Database session (injected).
        current_user: Authenticated user from JWT (injected).

    Returns:
        The created attachment metadata.

    Raises:
        HTTPException: 404 if ticket not found, 403 if no access,
            400 if file processing fails.
    """
    result = await db.execute(
        select(Ticket).where(Ticket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )

    is_owner = ticket.user_id == current_user["user_id"]
    is_privileged = _is_staff(current_user["role"])

    if not is_owner and not is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this ticket",
        )

    content = await file.read()

    try:
        saved_filename = await async_save_upload(content, file.filename or "upload")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    attachment = TicketAttachment(
        ticket_id=ticket.id,
        user_id=current_user["user_id"],
        filename=file.filename or "upload",
        filepath=f"/static/{saved_filename}",
        content_type=file.content_type or "application/octet-stream",
        file_size=len(content),
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)

    return AttachmentResponse(
        id=attachment.id,
        ticket_id=attachment.ticket_id,
        filename=attachment.filename,
        filepath=attachment.filepath,
        content_type=attachment.content_type,
        file_size=attachment.file_size,
        uploaded_at=attachment.uploaded_at,
    )
