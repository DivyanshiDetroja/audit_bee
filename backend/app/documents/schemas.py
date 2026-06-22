import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    uploaded_by: uuid.UUID
    original_filename: str
    normalized_filename: str | None
    storage_key: str
    doc_type: str | None
    tax_year: int | None
    mime_type: str | None
    status: str
    source_channel: str
    extracted_summary: str | None
    extracted_fields: dict[str, Any] | None
    uploaded_at: datetime
    processed_at: datetime | None


class DocumentStatusOut(BaseModel):
    """Lightweight payload for the polling status endpoint."""

    id: uuid.UUID
    status: str
    doc_type: str | None
    tax_year: int | None
    normalized_filename: str | None
    extracted_summary: str | None
    processed_at: datetime | None
