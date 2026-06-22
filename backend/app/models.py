import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Enums ──────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    admin = "admin"
    cpa = "cpa"
    client = "client"


class ClientType(str, enum.Enum):
    individual = "individual"
    business = "business"


class DocumentStatus(str, enum.Enum):
    processing = "processing"
    classified = "classified"
    needs_review = "needs_review"
    error = "error"


class SourceChannel(str, enum.Enum):
    portal = "portal"
    email_sim = "email_sim"
    scan_sim = "scan_sim"


class RequiredDocStatus(str, enum.Enum):
    pending = "pending"
    received = "received"


class ContextSource(str, enum.Enum):
    document = "document"
    cpa_note = "cpa_note"
    probe_answer = "probe_answer"


class ProbeStatus(str, enum.Enum):
    open = "open"
    answered = "answered"


class ReminderChannel(str, enum.Enum):
    email_sim = "email_sim"


class ReminderStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    scheduled = "scheduled"


class IntegrationStatus(str, enum.Enum):
    connected = "connected"
    disconnected = "disconnected"


# ── Models ─────────────────────────────────────────────────────────────────────

class Firm(Base):
    __tablename__ = "firms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    users: Mapped[list["User"]] = relationship("User", foreign_keys="User.firm_id", back_populates="firm")
    clients: Mapped[list["Client"]] = relationship(back_populates="firm")
    integrations: Mapped[list["Integration"]] = relationship(back_populates="firm")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("firms.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole, name="userrole"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Only set for client-role users. FK is deferred (use_alter) because clients
    # table doesn't exist yet when users is created — added as ALTER TABLE after.
    client_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", use_alter=True, name="fk_users_client_id"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    firm: Mapped["Firm"] = relationship("Firm", foreign_keys="User.firm_id", back_populates="users")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user", foreign_keys="AuditLog.user_id")


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("firms.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[ClientType] = mapped_column(SAEnum(ClientType, name="clienttype"), nullable=False)
    assigned_cpa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    tax_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    invite_token_jti: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    firm: Mapped["Firm"] = relationship(back_populates="clients")
    assigned_cpa: Mapped["User | None"] = relationship("User", foreign_keys=[assigned_cpa_id])
    documents: Mapped[list["Document"]] = relationship(back_populates="client")
    required_documents: Mapped[list["RequiredDocument"]] = relationship(back_populates="client")
    context_entries: Mapped[list["ContextEntry"]] = relationship(back_populates="client")
    context_probes: Mapped[list["ContextProbe"]] = relationship(back_populates="client")
    reminders: Mapped[list["Reminder"]] = relationship(back_populates="client")


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    doc_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tax_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[DocumentStatus] = mapped_column(
        SAEnum(DocumentStatus, name="documentstatus"),
        nullable=False,
        server_default="processing",
    )
    extracted_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    source_channel: Mapped[SourceChannel] = mapped_column(
        SAEnum(SourceChannel, name="sourcechannel"),
        nullable=False,
        server_default="portal",
    )
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    client: Mapped["Client"] = relationship(back_populates="documents")
    uploader: Mapped["User"] = relationship("User", foreign_keys=[uploaded_by])


class RequiredDocument(Base):
    __tablename__ = "required_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    status: Mapped[RequiredDocStatus] = mapped_column(
        SAEnum(RequiredDocStatus, name="requireddocstatus"),
        nullable=False,
        server_default="pending",
    )
    satisfied_by_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id"), nullable=True
    )

    client: Mapped["Client"] = relationship(back_populates="required_documents")
    satisfied_by: Mapped["Document | None"] = relationship("Document", foreign_keys=[satisfied_by_document_id])


class ContextEntry(Base):
    __tablename__ = "context_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[ContextSource] = mapped_column(SAEnum(ContextSource, name="contextsource"), nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    client: Mapped["Client"] = relationship(back_populates="context_entries")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])


class ContextProbe(Base):
    __tablename__ = "context_probes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ProbeStatus] = mapped_column(
        SAEnum(ProbeStatus, name="probestatus"),
        nullable=False,
        server_default="open",
    )
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    answered_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    client: Mapped["Client"] = relationship(back_populates="context_probes")
    answerer: Mapped["User | None"] = relationship("User", foreign_keys=[answered_by])


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    channel: Mapped[ReminderChannel] = mapped_column(
        SAEnum(ReminderChannel, name="reminderchannel"),
        nullable=False,
        server_default="email_sim",
    )
    draft_subject: Mapped[str | None] = mapped_column(String(500), nullable=True)
    draft_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ReminderStatus] = mapped_column(
        SAEnum(ReminderStatus, name="reminderstatus"),
        nullable=False,
        server_default="draft",
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    client: Mapped["Client"] = relationship(back_populates="reminders")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Nullable so pre-auth events (e.g. failed login) can be logged without a user
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User | None"] = relationship(back_populates="audit_logs", foreign_keys=[user_id])


class Integration(Base):
    __tablename__ = "integrations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firm_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("firms.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[IntegrationStatus] = mapped_column(
        SAEnum(IntegrationStatus, name="integrationstatus"),
        nullable=False,
        server_default="disconnected",
    )
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    firm: Mapped["Firm"] = relationship(back_populates="integrations")
