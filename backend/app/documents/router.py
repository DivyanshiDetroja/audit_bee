import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.audit import log_event
from app.auth.dependencies import authorize_client_access, get_current_user
from app.documents.schemas import DocumentOut, DocumentStatusOut
from app.documents.validation import validate_upload
from app import storage
from app.database import get_db
from app.models import Document, DocumentStatus, SourceChannel, User
from app.pipeline import process_document

router = APIRouter(tags=["documents"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _get_doc_or_404(
    db: Session, document_id: uuid.UUID, client_id: uuid.UUID
) -> Document:
    """Always filter by both document_id AND client_id — closes cross-client IDOR."""
    doc = db.query(Document).filter_by(id=document_id, client_id=client_id).first()
    if not doc:
        raise HTTPException(status_code=404)
    return doc


# ── Upload ─────────────────────────────────────────────────────────────────────

@router.post("/clients/{client_id}/documents", status_code=201, response_model=DocumentOut)
def upload_document(
    client_id: uuid.UUID,
    file: UploadFile,
    request: Request,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    client = authorize_client_access(client_id, current_user, db)

    data = file.file.read()
    mime = validate_upload(data)

    storage_key = str(uuid.uuid4())
    storage.save_file(storage_key, data)

    doc = Document(
        client_id=client.id,
        uploaded_by=current_user.id,
        original_filename=file.filename or "upload",
        storage_key=storage_key,
        mime_type=mime,
        status=DocumentStatus.processing,
        source_channel=SourceChannel.portal,
    )
    db.add(doc)
    db.flush()

    log_event(
        db,
        user_id=current_user.id,
        action="document_upload",
        resource_type="document",
        resource_id=str(doc.id),
        ip=_ip(request),
        detail={
            "client_id": str(client.id),
            "filename": doc.original_filename,
            "mime": mime,
            "size_bytes": len(data),
        },
    )
    db.commit()
    db.refresh(doc)

    # Kick off background processing — runs after the response is sent
    background_tasks.add_task(process_document, doc.id)

    return doc


# ── List ───────────────────────────────────────────────────────────────────────

@router.get("/clients/{client_id}/documents", response_model=list[DocumentOut])
def list_documents(
    client_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Document]:
    client = authorize_client_access(client_id, current_user, db)

    docs = (
        db.query(Document)
        .filter_by(client_id=client.id)
        .order_by(Document.uploaded_at.desc())
        .all()
    )

    log_event(
        db,
        user_id=current_user.id,
        action="document_list",
        resource_type="client",
        resource_id=str(client.id),
        ip=_ip(request),
    )
    db.commit()
    return docs


# ── Get metadata ───────────────────────────────────────────────────────────────

@router.get("/clients/{client_id}/documents/{document_id}", response_model=DocumentOut)
def get_document(
    client_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    client = authorize_client_access(client_id, current_user, db)
    doc = _get_doc_or_404(db, document_id, client.id)

    log_event(
        db,
        user_id=current_user.id,
        action="document_view",
        resource_type="document",
        resource_id=str(doc.id),
        ip=_ip(request),
    )
    db.commit()
    return doc


# ── Status (poll endpoint for Processing → Classified) ─────────────────────────

@router.get(
    "/clients/{client_id}/documents/{document_id}/status",
    response_model=DocumentStatusOut,
)
def get_document_status(
    client_id: uuid.UUID,
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Document:
    """Lightweight endpoint for the frontend to poll until status != 'processing'."""
    client = authorize_client_access(client_id, current_user, db)
    return _get_doc_or_404(db, document_id, client.id)


# ── Download (stream) ──────────────────────────────────────────────────────────

@router.get("/clients/{client_id}/documents/{document_id}/download")
def download_document(
    client_id: uuid.UUID,
    document_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    client = authorize_client_access(client_id, current_user, db)
    doc = _get_doc_or_404(db, document_id, client.id)

    try:
        data = storage.load_file(doc.storage_key)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found in storage")

    log_event(
        db,
        user_id=current_user.id,
        action="document_download",
        resource_type="document",
        resource_id=str(doc.id),
        ip=_ip(request),
        detail={"client_id": str(client.id), "filename": doc.original_filename},
    )
    db.commit()

    safe_filename = doc.original_filename.replace('"', "")
    return Response(
        content=data,
        media_type=doc.mime_type or "application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}"',
            "Content-Length": str(len(data)),
        },
    )
