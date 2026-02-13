"""Ticket request/response schemas for support ticket system.

Defines Pydantic v2 models for ticket CRUD, messages with internal-note
flag, and file attachments. The is_internal field on messages is central
to VULN 3 (internal notes leak via forged JWT role).
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class CreateTicketRequest(BaseModel):
    """Payload for creating a new support ticket."""

    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1)


class CreateMessageRequest(BaseModel):
    """Payload for adding a message to an existing ticket."""

    body: str = Field(min_length=1)
    is_internal: bool = Field(default=False)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class TicketMessageResponse(BaseModel):
    """Single message within a ticket thread."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    user_id: int
    username: str
    body: str
    is_internal: bool
    created_at: datetime


class TicketResponse(BaseModel):
    """Full ticket with all messages."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    subject: str
    status: str
    priority: str
    created_at: datetime
    updated_at: datetime
    messages: list[TicketMessageResponse]


class TicketSummaryResponse(BaseModel):
    """Compact ticket view for list endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    subject: str
    status: str
    priority: str
    created_at: datetime


class AttachmentResponse(BaseModel):
    """File attachment metadata for a ticket."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket_id: int
    filename: str
    filepath: str
    content_type: str
    file_size: int
    uploaded_at: datetime
