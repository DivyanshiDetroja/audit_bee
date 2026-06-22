"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-21

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── firms ──────────────────────────────────────────────────────────────────
    op.create_table(
        "firms",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── users ──────────────────────────────────────────────────────────────────
    # client_id column is present but the FK to clients is added after that table
    # is created (deferred ALTER TABLE below).
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("firms.id"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("admin", "cpa", "client", name="userrole"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # ── clients ────────────────────────────────────────────────────────────────
    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("firms.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.Enum("individual", "business", name="clienttype"), nullable=False),
        sa.Column("assigned_cpa_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("tax_year", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # Deferred FK: users.client_id → clients.id
    op.create_foreign_key("fk_users_client_id", "users", "clients", ["client_id"], ["id"])

    # ── documents ──────────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("normalized_filename", sa.String(255), nullable=True),
        sa.Column("storage_key", sa.String(255), nullable=False, unique=True),
        sa.Column("doc_type", sa.String(50), nullable=True),
        sa.Column("tax_year", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("processing", "classified", "needs_review", "error", name="documentstatus"),
            nullable=False,
            server_default="processing",
        ),
        sa.Column("extracted_summary", sa.Text(), nullable=True),
        sa.Column("extracted_fields", postgresql.JSONB(), nullable=True),
        sa.Column(
            "source_channel",
            sa.Enum("portal", "email_sim", "scan_sim", name="sourcechannel"),
            nullable=False,
            server_default="portal",
        ),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── required_documents ─────────────────────────────────────────────────────
    op.create_table(
        "required_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("doc_type", sa.String(50), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "received", name="requireddocstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("satisfied_by_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id"), nullable=True),
    )

    # ── context_entries ────────────────────────────────────────────────────────
    op.create_table(
        "context_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.Enum("document", "cpa_note", "probe_answer", name="contextsource"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── context_probes ─────────────────────────────────────────────────────────
    op.create_table(
        "context_probes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("open", "answered", name="probestatus"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("answered_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
    )

    # ── reminders ──────────────────────────────────────────────────────────────
    op.create_table(
        "reminders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
        sa.Column(
            "channel",
            sa.Enum("email_sim", name="reminderchannel"),
            nullable=False,
            server_default="email_sim",
        ),
        sa.Column("draft_subject", sa.String(500), nullable=True),
        sa.Column("draft_body", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("draft", "sent", "scheduled", name="reminderstatus"),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── audit_logs ─────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("ip", sa.String(45), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    # ── integrations ───────────────────────────────────────────────────────────
    op.create_table(
        "integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("firm_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("firms.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "status",
            sa.Enum("connected", "disconnected", name="integrationstatus"),
            nullable=False,
            server_default="disconnected",
        ),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("integrations")
    op.drop_table("audit_logs")
    op.drop_table("reminders")
    op.drop_table("context_probes")
    op.drop_table("context_entries")
    op.drop_table("required_documents")
    op.drop_table("documents")
    op.drop_constraint("fk_users_client_id", "users", type_="foreignkey")
    op.drop_table("clients")
    op.drop_table("users")
    op.drop_table("firms")

    for name in (
        "integrationstatus",
        "reminderstatus",
        "reminderchannel",
        "probestatus",
        "contextsource",
        "requireddocstatus",
        "sourcechannel",
        "documentstatus",
        "clienttype",
        "userrole",
    ):
        sa.Enum(name=name).drop(op.get_bind(), checkfirst=True)
