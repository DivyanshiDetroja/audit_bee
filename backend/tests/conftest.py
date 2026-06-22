"""
Shared pytest fixtures.

test_setup creates a complete isolated graph (firm → cpa, client_a, client_b,
user_a) and tears it down fully — including files on disk — after each test.
"""

import uuid

import pytest
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session

from app import storage
from app.auth.service import create_access_token, hash_password
from app.database import SessionLocal
from app.models import (
    AuditLog,
    Client,
    ClientType,
    ContextEntry,
    ContextProbe,
    Document,
    Firm,
    Integration,
    IntegrationStatus,
    Reminder,
    RequiredDocument,
    User,
    UserRole,
)


@pytest.fixture(scope="function")
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def test_setup(db: Session) -> dict:
    """
    Builds an isolated test dataset and tears it down after the test.

    Yields a dict with: firm, admin, cpa, client_a, client_b, user_a,
    admin_token, cpa_token, user_a_token.
    """
    tag = uuid.uuid4().hex[:8]

    firm = Firm(name=f"test-firm-{tag}")
    db.add(firm)
    db.flush()

    # Seed demo integrations for the test firm (matches seed.py behaviour)
    for name in ["Gmail", "DocuSign", "Calendly", "QuickBooks"]:
        db.add(Integration(firm_id=firm.id, name=name, status=IntegrationStatus.connected))
    db.flush()

    admin = User(
        firm_id=firm.id,
        email=f"admin-{tag}@test.local",
        password_hash=hash_password("Test1234!"),
        role=UserRole.admin,
        name="Test Admin",
    )
    db.add(admin)
    db.flush()

    cpa = User(
        firm_id=firm.id,
        email=f"cpa-{tag}@test.local",
        password_hash=hash_password("Test1234!"),
        role=UserRole.cpa,
        name="Test CPA",
    )
    db.add(cpa)
    db.flush()

    client_a = Client(
        firm_id=firm.id,
        name="Client A",
        type=ClientType.individual,
        assigned_cpa_id=cpa.id,
    )
    client_b = Client(
        firm_id=firm.id,
        name="Client B",
        type=ClientType.individual,
        assigned_cpa_id=cpa.id,
    )
    db.add_all([client_a, client_b])
    db.flush()

    user_a = User(
        firm_id=firm.id,
        email=f"user-a-{tag}@test.local",
        password_hash=hash_password("Test1234!"),
        role=UserRole.client,
        name="User A",
        client_id=client_a.id,
    )
    db.add(user_a)
    db.commit()

    yield {
        "firm": firm,
        "admin": admin,
        "cpa": cpa,
        "client_a": client_a,
        "client_b": client_b,
        "user_a": user_a,
        "admin_token": create_access_token(
            str(admin.id), admin.role.value, str(firm.id), None
        ),
        "cpa_token": create_access_token(
            str(cpa.id), cpa.role.value, str(firm.id), None
        ),
        "user_a_token": create_access_token(
            str(user_a.id), user_a.role.value, str(firm.id), str(client_a.id)
        ),
    }

    # ── Teardown ────────────────────────────────────────────────────────────────
    # 1. Collect storage keys before deleting document rows so we can clean disk
    docs = (
        db.query(Document)
        .filter(Document.client_id.in_([client_a.id, client_b.id]))
        .all()
    )
    for doc in docs:
        try:
            storage.delete_file(doc.storage_key)
        except Exception:
            pass

    # 2. Delete child rows in FK-safe order
    db.query(AuditLog).filter(
        AuditLog.user_id.in_([admin.id, cpa.id, user_a.id])
    ).delete(synchronize_session=False)

    db.query(ContextEntry).filter(
        ContextEntry.client_id.in_([client_a.id, client_b.id])
    ).delete(synchronize_session=False)

    db.query(ContextProbe).filter(
        ContextProbe.client_id.in_([client_a.id, client_b.id])
    ).delete(synchronize_session=False)

    # Reminder.created_by → users; must be deleted before users.
    db.query(Reminder).filter(
        Reminder.client_id.in_([client_a.id, client_b.id])
    ).delete(synchronize_session=False)

    # RequiredDocument has a FK to Document (satisfied_by_document_id);
    # must be deleted before documents to avoid FK violations.
    db.query(RequiredDocument).filter(
        RequiredDocument.client_id.in_([client_a.id, client_b.id])
    ).delete(synchronize_session=False)

    db.query(Document).filter(
        Document.client_id.in_([client_a.id, client_b.id])
    ).delete(synchronize_session=False)

    # 3. Clear user_a.client_id before deleting clients (deferred FK)
    db.execute(
        sa_update(User).where(User.id == user_a.id).values(client_id=None)
    )
    db.flush()

    db.query(Client).filter(
        Client.id.in_([client_a.id, client_b.id])
    ).delete(synchronize_session=False)

    db.query(User).filter(
        User.id.in_([user_a.id, cpa.id, admin.id])
    ).delete(synchronize_session=False)

    db.query(Integration).filter_by(firm_id=firm.id).delete(synchronize_session=False)

    db.query(Firm).filter_by(id=firm.id).delete()
    db.commit()
