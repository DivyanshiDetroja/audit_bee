import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from app.audit import log_event
from app.auth.dependencies import (
    authorize_client_access,
    get_current_user,
    require_role,
)
from app.checklist import seed_checklist
from app.clients.schemas import (
    AnswerProbeIn,
    ContextEntryOut,
    ContextProbeOut,
    ReminderOut,
    RequiredDocumentOut,
    SendReminderIn,
)
from app.database import get_db
from app.documents.schemas import DocumentOut
from app.documents.validation import validate_upload
from app import storage
from app.models import (
    Client,
    ContextEntry,
    ContextProbe,
    ContextSource,
    Document,
    DocumentStatus,
    ProbeStatus,
    Reminder,
    ReminderStatus,
    RequiredDocument,
    RequiredDocStatus,
    SourceChannel,
    User,
    UserRole,
)
from app.pipeline import process_document
from app.reminders import draft_reminder

router = APIRouter(tags=["clients"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# ── Checklist ──────────────────────────────────────────────────────────────────

@router.get("/clients/{client_id}/checklist", response_model=list[RequiredDocumentOut])
def get_checklist(
    client_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RequiredDocument]:
    client = authorize_client_access(client_id, current_user, db)
    return (
        db.query(RequiredDocument)
        .filter_by(client_id=client.id)
        .order_by(RequiredDocument.doc_type)
        .all()
    )


@router.get("/clients/{client_id}/pending", response_model=list[RequiredDocumentOut])
def get_pending(
    client_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[RequiredDocument]:
    client = authorize_client_access(client_id, current_user, db)
    return (
        db.query(RequiredDocument)
        .filter_by(client_id=client.id, status=RequiredDocStatus.pending)
        .order_by(RequiredDocument.doc_type)
        .all()
    )


@router.post(
    "/clients/{client_id}/checklist/seed",
    response_model=list[RequiredDocumentOut],
    status_code=201,
)
def seed_client_checklist(
    client_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.cpa)),
    db: Session = Depends(get_db),
) -> list[RequiredDocument]:
    """Seed the required-document checklist for a client.  Idempotent."""
    client = authorize_client_access(client_id, current_user, db)
    items = seed_checklist(client, db)
    if not items:
        return (
            db.query(RequiredDocument)
            .filter_by(client_id=client.id)
            .order_by(RequiredDocument.doc_type)
            .all()
        )
    db.commit()
    for item in items:
        db.refresh(item)
    return items


# ── Context trail ──────────────────────────────────────────────────────────────

@router.get("/clients/{client_id}/context", response_model=list[ContextEntryOut])
def get_context(
    client_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ContextEntry]:
    client = authorize_client_access(client_id, current_user, db)
    return (
        db.query(ContextEntry)
        .filter_by(client_id=client.id)
        .order_by(ContextEntry.created_at.desc())
        .all()
    )


# ── Context probes ─────────────────────────────────────────────────────────────

@router.get("/clients/{client_id}/probes", response_model=list[ContextProbeOut])
def list_probes(
    client_id: uuid.UUID,
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ContextProbe]:
    """List context probes.  Optionally filter with ?status=open or ?status=answered."""
    client = authorize_client_access(client_id, current_user, db)
    q = db.query(ContextProbe).filter_by(client_id=client.id)
    if status:
        q = q.filter(ContextProbe.status == status)
    return q.order_by(ContextProbe.created_at.desc()).all()


@router.post(
    "/clients/{client_id}/probes/{probe_id}/answer",
    response_model=ContextProbeOut,
)
def answer_probe(
    client_id: uuid.UUID,
    probe_id: uuid.UUID,
    body: AnswerProbeIn,
    request: Request,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.cpa)),
    db: Session = Depends(get_db),
) -> ContextProbe:
    """Answer an open context probe.  Appends a ContextEntry for the audit trail."""
    client = authorize_client_access(client_id, current_user, db)

    probe = (
        db.query(ContextProbe)
        .filter_by(id=probe_id, client_id=client.id)
        .first()
    )
    if not probe:
        raise HTTPException(status_code=404)
    if probe.status != ProbeStatus.open:
        raise HTTPException(status_code=409, detail="Probe already answered")

    probe.status = ProbeStatus.answered
    probe.answer = body.answer
    probe.answered_by = current_user.id

    entry = ContextEntry(
        client_id=client.id,
        content=f"CPA answered a context question.\nQ: {probe.question}\nA: {body.answer}",
        source=ContextSource.probe_answer,
        created_by=current_user.id,
    )
    db.add(entry)

    log_event(
        db,
        user_id=current_user.id,
        action="probe_answered",
        resource_type="context_probe",
        resource_id=str(probe.id),
        ip=_ip(request),
        detail={"client_id": str(client.id)},
    )
    db.commit()
    db.refresh(probe)
    return probe


# ── Reminders ──────────────────────────────────────────────────────────────────

@router.post(
    "/clients/{client_id}/reminders/draft",
    response_model=ReminderOut,
    status_code=201,
)
def draft_client_reminder(
    client_id: uuid.UUID,
    request: Request,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.cpa)),
    db: Session = Depends(get_db),
) -> Reminder:
    """
    Build the pending list and ask Claude to draft a reminder email.
    Returns a Reminder with status=draft for the CPA to review and edit.
    """
    client = authorize_client_access(client_id, current_user, db)

    try:
        reminder = draft_reminder(client, current_user.id, db)
    except ValueError as exc:
        if str(exc) == "no_pending":
            raise HTTPException(
                status_code=422,
                detail="No pending documents — nothing to remind the client about.",
            )
        raise HTTPException(status_code=503, detail="Reminder draft failed.")
    except Exception:
        raise HTTPException(status_code=503, detail="Reminder draft failed.")

    log_event(
        db,
        user_id=current_user.id,
        action="reminder_drafted",
        resource_type="client",
        resource_id=str(client.id),
        ip=_ip(request),
    )
    db.commit()
    db.refresh(reminder)
    return reminder


@router.get("/clients/{client_id}/reminders", response_model=list[ReminderOut])
def list_reminders(
    client_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Reminder]:
    client = authorize_client_access(client_id, current_user, db)
    return (
        db.query(Reminder)
        .filter_by(client_id=client.id)
        .order_by(Reminder.sent_at.desc().nullslast(), Reminder.created_by)
        .all()
    )


@router.post(
    "/clients/{client_id}/reminders/{reminder_id}/send",
    response_model=ReminderOut,
)
def send_reminder(
    client_id: uuid.UUID,
    reminder_id: uuid.UUID,
    body: SendReminderIn,
    request: Request,
    current_user: User = Depends(require_role(UserRole.admin, UserRole.cpa)),
    db: Session = Depends(get_db),
) -> Reminder:
    """
    'Send' a draft reminder (simulated — logged + status=sent).
    The CPA can supply an edited subject/body; omit either field to keep the draft.
    Nothing is auto-sent (DESIGN.md §6.6).
    """
    client = authorize_client_access(client_id, current_user, db)

    reminder = (
        db.query(Reminder)
        .filter_by(id=reminder_id, client_id=client.id)
        .first()
    )
    if not reminder:
        raise HTTPException(status_code=404)
    if reminder.status == ReminderStatus.sent:
        raise HTTPException(status_code=409, detail="Reminder already sent")

    if body.subject is not None:
        reminder.draft_subject = body.subject
    if body.body is not None:
        reminder.draft_body = body.body

    reminder.status = ReminderStatus.sent
    reminder.sent_at = datetime.now(timezone.utc)

    log_event(
        db,
        user_id=current_user.id,
        action="reminder_sent",
        resource_type="reminder",
        resource_id=str(reminder.id),
        ip=_ip(request),
        detail={
            "client_id": str(client.id),
            "subject": reminder.draft_subject,
            "channel": reminder.channel.value,
        },
    )
    db.commit()
    db.refresh(reminder)
    return reminder


# ── Simulate inbound email (DESIGN.md §6.8) ────────────────────────────────────
# DEMO SIMULATION: no real email connection is built.  This endpoint mimics a
# document arriving via Gmail/email by injecting it into the client's intake
# with source_channel=email_sim.  The identical Phase 4 pipeline runs on it —
# the channel-agnostic design is the point being demonstrated.

@router.post(
    "/clients/{client_id}/simulate-email",
    response_model=DocumentOut,
    status_code=201,
)
def simulate_inbound_email(
    client_id: uuid.UUID,
    file: UploadFile,
    request: Request,
    background_tasks: BackgroundTasks,
    from_address: str = Form(default="client@email.example.com"),
    current_user: User = Depends(require_role(UserRole.admin, UserRole.cpa)),
    db: Session = Depends(get_db),
) -> Document:
    """
    Simulate a document arriving via inbound email (DEMO — no real email
    integration).  Identical to a portal upload except source_channel=email_sim.
    The same Phase 4 classification pipeline runs on the injected document.
    """
    client = authorize_client_access(client_id, current_user, db)

    data = file.file.read()
    mime = validate_upload(data)

    storage_key = str(uuid.uuid4())
    storage.save_file(storage_key, data)

    doc = Document(
        client_id=client.id,
        uploaded_by=current_user.id,
        original_filename=file.filename or "email_attachment",
        storage_key=storage_key,
        mime_type=mime,
        status=DocumentStatus.processing,
        # DEMO SIMULATION: marks this document as arriving via the email channel.
        source_channel=SourceChannel.email_sim,
    )
    db.add(doc)
    db.flush()

    log_event(
        db,
        user_id=current_user.id,
        action="document_upload_email_sim",
        resource_type="document",
        resource_id=str(doc.id),
        ip=request.client.host if request.client else None,
        detail={
            "client_id": str(client.id),
            "filename": doc.original_filename,
            "mime": mime,
            "from_address": from_address,
            "size_bytes": len(data),
        },
    )
    db.commit()
    db.refresh(doc)

    background_tasks.add_task(process_document, doc.id)
    return doc
