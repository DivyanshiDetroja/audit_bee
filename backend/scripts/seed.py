"""
Seed one Firm and one admin User.
Run inside the backend container:
    docker compose exec backend python scripts/seed.py
"""

import os
import sys
import uuid

# Allow importing app modules when run as a script
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from argon2 import PasswordHasher
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Firm, Integration, IntegrationStatus, User, UserRole

FIRM_NAME = "Acme CPA Partners"
ADMIN_EMAIL = "admin@acmecpa.com"
ADMIN_NAME = "Admin User"
ADMIN_PASSWORD = "Admin1234!"


def seed(db: Session) -> None:
    # Idempotent: skip if already seeded
    existing = db.query(User).filter_by(email=ADMIN_EMAIL).first()
    if existing:
        print(f"Already seeded — admin user {ADMIN_EMAIL} exists.")
        return

    firm = Firm(id=uuid.uuid4(), name=FIRM_NAME)
    db.add(firm)
    db.flush()

    ph = PasswordHasher()
    admin = User(
        id=uuid.uuid4(),
        firm_id=firm.id,
        email=ADMIN_EMAIL,
        password_hash=ph.hash(ADMIN_PASSWORD),
        role=UserRole.admin,
        name=ADMIN_NAME,
        is_active=True,
    )
    db.add(admin)
    db.commit()

    # Seed demo integrations (DESIGN.md §6.8 — simulated, not real OAuth).
    # All start as "connected" to show the Connections page story on open.
    _DEMO_INTEGRATIONS = ["Gmail", "DocuSign", "Calendly", "QuickBooks"]
    for name in _DEMO_INTEGRATIONS:
        db.add(Integration(
            firm_id=firm.id,
            name=name,
            status=IntegrationStatus.connected,
        ))
    db.commit()

    print(f"Seeded firm:  {firm.name}  ({firm.id})")
    print(f"Seeded admin: {admin.email}  ({admin.id})")
    print(f"Password:     {ADMIN_PASSWORD}")
    print(f"Seeded integrations: {', '.join(_DEMO_INTEGRATIONS)}")


if __name__ == "__main__":
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()
