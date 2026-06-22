import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RequiredDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    doc_type: str
    label: str
    required: bool
    status: str
    satisfied_by_document_id: uuid.UUID | None


class ContextEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    content: str
    source: str
    created_by: uuid.UUID
    created_at: datetime


class ContextProbeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    question: str
    status: str
    answer: str | None
    created_at: datetime
    answered_by: uuid.UUID | None


class AnswerProbeIn(BaseModel):
    answer: str


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    channel: str
    draft_subject: str | None
    draft_body: str | None
    status: str
    scheduled_for: datetime | None
    created_by: uuid.UUID
    sent_at: datetime | None


class SendReminderIn(BaseModel):
    subject: str | None = None
    body: str | None = None
