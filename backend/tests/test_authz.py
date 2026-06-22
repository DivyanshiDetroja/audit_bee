"""
Unit tests for authorize_client_access (DESIGN.md §6.7).

These tests exercise the authorization logic directly — no HTTP layer, no DB.
The database is mocked so the tests run anywhere without docker-compose.

Key invariants proved:
  - A client cannot access another client's resource            → 404
  - A CPA cannot access a client they are not assigned to       → 404
  - A client from a different firm gets 404 (existence hidden)  → 404
  - A nonexistent resource returns 404                          → 404
  - A client CAN access their own resource                      → passes
  - A CPA CAN access their assigned client                      → passes
  - An admin CAN access any client within their firm            → passes
  - An admin CANNOT access a client in a different firm         → 404
"""

import uuid
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.auth.dependencies import authorize_client_access
from app.models import UserRole


# ── Helpers ────────────────────────────────────────────────────────────────────

def _user(
    role: UserRole,
    firm_id: uuid.UUID,
    client_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> MagicMock:
    u = MagicMock()
    u.id = user_id or uuid.uuid4()
    u.role = role
    u.firm_id = firm_id
    u.client_id = client_id
    return u


def _client(
    firm_id: uuid.UUID,
    assigned_cpa_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None = None,
) -> MagicMock:
    c = MagicMock()
    c.id = client_id or uuid.uuid4()
    c.firm_id = firm_id
    c.assigned_cpa_id = assigned_cpa_id
    return c


def _db(returning) -> MagicMock:
    """Return a mock DB session whose .query().filter_by().first() yields `returning`."""
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = returning
    return db


# ── Client role ────────────────────────────────────────────────────────────────

class TestClientAccess:
    def test_client_cannot_access_another_clients_resource(self):
        """Core no-leak test: client A must not see client B's data."""
        firm = uuid.uuid4()
        client_a_id = uuid.uuid4()
        client_b = _client(firm)

        user = _user(UserRole.client, firm, client_id=client_a_id)

        with pytest.raises(HTTPException) as exc:
            authorize_client_access(client_b.id, user, _db(client_b))

        assert exc.value.status_code == 404

    def test_client_can_access_own_resource(self):
        firm = uuid.uuid4()
        client = _client(firm)
        user = _user(UserRole.client, firm, client_id=client.id)

        result = authorize_client_access(client.id, user, _db(client))

        assert result is client

    def test_client_from_different_firm_gets_404(self):
        """Cross-firm access must be invisible — same 404 as a missing resource."""
        firm_a = uuid.uuid4()
        firm_b = uuid.uuid4()
        # The resource lives in firm_b
        foreign_client = _client(firm_b)
        # The caller belongs to firm_a
        user = _user(UserRole.client, firm_a, client_id=uuid.uuid4())

        with pytest.raises(HTTPException) as exc:
            authorize_client_access(foreign_client.id, user, _db(foreign_client))

        assert exc.value.status_code == 404

    def test_nonexistent_resource_returns_404(self):
        firm = uuid.uuid4()
        user = _user(UserRole.client, firm, client_id=uuid.uuid4())

        with pytest.raises(HTTPException) as exc:
            authorize_client_access(uuid.uuid4(), user, _db(None))

        assert exc.value.status_code == 404


# ── CPA role ───────────────────────────────────────────────────────────────────

class TestCpaAccess:
    def test_cpa_cannot_access_unassigned_client(self):
        """Core no-leak test: CPA must not see a client assigned to another CPA."""
        firm = uuid.uuid4()
        cpa = _user(UserRole.cpa, firm)
        other_cpa_id = uuid.uuid4()

        client = _client(firm, assigned_cpa_id=other_cpa_id)

        with pytest.raises(HTTPException) as exc:
            authorize_client_access(client.id, cpa, _db(client))

        assert exc.value.status_code == 404

    def test_cpa_can_access_assigned_client(self):
        firm = uuid.uuid4()
        cpa = _user(UserRole.cpa, firm)
        client = _client(firm, assigned_cpa_id=cpa.id)

        result = authorize_client_access(client.id, cpa, _db(client))

        assert result is client

    def test_cpa_cannot_access_unassigned_client_even_same_firm(self):
        """Assignment check is separate from firm check."""
        firm = uuid.uuid4()
        cpa = _user(UserRole.cpa, firm)
        # Client exists in the same firm but is unassigned (no CPA set)
        unassigned_client = _client(firm, assigned_cpa_id=None)

        with pytest.raises(HTTPException) as exc:
            authorize_client_access(unassigned_client.id, cpa, _db(unassigned_client))

        assert exc.value.status_code == 404

    def test_cpa_cannot_access_client_in_different_firm(self):
        firm_a = uuid.uuid4()
        firm_b = uuid.uuid4()
        cpa = _user(UserRole.cpa, firm_a)
        # Client in firm_b happens to list this CPA's id (cross-firm smuggle attempt)
        foreign_client = _client(firm_b, assigned_cpa_id=cpa.id)

        with pytest.raises(HTTPException) as exc:
            authorize_client_access(foreign_client.id, cpa, _db(foreign_client))

        assert exc.value.status_code == 404


# ── Admin role ─────────────────────────────────────────────────────────────────

class TestAdminAccess:
    def test_admin_can_access_any_client_in_their_firm(self):
        firm = uuid.uuid4()
        admin = _user(UserRole.admin, firm)
        # Client assigned to some CPA — admin should still see it
        client = _client(firm, assigned_cpa_id=uuid.uuid4())

        result = authorize_client_access(client.id, admin, _db(client))

        assert result is client

    def test_admin_cannot_access_client_in_different_firm(self):
        firm_a = uuid.uuid4()
        firm_b = uuid.uuid4()
        admin = _user(UserRole.admin, firm_a)
        foreign_client = _client(firm_b)

        with pytest.raises(HTTPException) as exc:
            authorize_client_access(foreign_client.id, admin, _db(foreign_client))

        assert exc.value.status_code == 404
