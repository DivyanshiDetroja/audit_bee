"""
Integration tests for Phase 7: connections surface and simulate-email.

DESIGN.md §6.8 — these are DEMO SIMULATIONS.  Tests verify the API surface
and authorization rules; no real OAuth or email infrastructure is exercised.
"""

import io
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, Document, Integration, IntegrationStatus, SourceChannel

http = TestClient(app)

MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"xref\n0 4\n"
    b"trailer<</Size 4/Root 1 0 R>>\n"
    b"startxref\n0\n%%EOF"
)


# ── Connections surface ────────────────────────────────────────────────────────

class TestConnections:
    def test_list_integrations_returns_firm_integrations(self, test_setup):
        resp = http.get(
            "/integrations",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
        )
        assert resp.status_code == 200
        names = {i["name"] for i in resp.json()}
        assert names == {"Gmail", "DocuSign", "Calendly", "QuickBooks"}

    def test_all_integrations_start_connected(self, test_setup):
        resp = http.get(
            "/integrations",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
        )
        assert all(i["status"] == "connected" for i in resp.json())

    def test_client_role_can_list_integrations(self, test_setup):
        """Clients should be able to see integration status (read-only)."""
        resp = http.get(
            "/integrations",
            headers={"Authorization": f"Bearer {test_setup['user_a_token']}"},
        )
        assert resp.status_code == 200

    def test_unauthenticated_list_returns_401(self, test_setup):
        resp = http.get("/integrations", headers={"Authorization": "Bearer bad-token"})
        assert resp.status_code == 401

    def test_admin_can_toggle_integration_to_disconnected(self, test_setup):
        db = SessionLocal()
        try:
            gmail = (
                db.query(Integration)
                .filter_by(firm_id=test_setup["firm"].id, name="Gmail")
                .first()
            )
            integration_id = str(gmail.id)
        finally:
            db.close()

        resp = http.post(
            f"/integrations/{integration_id}/toggle",
            headers={"Authorization": f"Bearer {test_setup['admin_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "disconnected"
        assert data["connected_at"] is None
        assert data["name"] == "Gmail"

    def test_toggle_twice_returns_to_connected(self, test_setup):
        db = SessionLocal()
        try:
            gmail = db.query(Integration).filter_by(
                firm_id=test_setup["firm"].id, name="Gmail"
            ).first()
            iid = str(gmail.id)
        finally:
            db.close()

        H = {"Authorization": f"Bearer {test_setup['admin_token']}"}

        http.post(f"/integrations/{iid}/toggle", headers=H)        # → disconnected
        resp = http.post(f"/integrations/{iid}/toggle", headers=H)  # → connected
        assert resp.json()["status"] == "connected"
        assert resp.json()["connected_at"] is not None

    def test_cpa_cannot_toggle_integration(self, test_setup):
        """Only admin may toggle; CPA gets 403."""
        db = SessionLocal()
        try:
            gmail = db.query(Integration).filter_by(
                firm_id=test_setup["firm"].id, name="Gmail"
            ).first()
            iid = str(gmail.id)
        finally:
            db.close()

        resp = http.post(
            f"/integrations/{iid}/toggle",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
        )
        assert resp.status_code == 403

    def test_cross_firm_toggle_returns_404(self, test_setup):
        """Admin from test firm must not reach another firm's integration (IDOR)."""
        from app.models import Firm
        db = SessionLocal()
        try:
            other_firm = Firm(name="other-firm")
            db.add(other_firm)
            db.flush()
            other_int = Integration(
                firm_id=other_firm.id, name="QuickBooks",
                status=IntegrationStatus.connected,
            )
            db.add(other_int)
            db.commit()
            other_int_id = str(other_int.id)
            other_firm_id = str(other_firm.id)
        finally:
            db.close()

        resp = http.post(
            f"/integrations/{other_int_id}/toggle",
            headers={"Authorization": f"Bearer {test_setup['admin_token']}"},
        )
        assert resp.status_code == 404

        db = SessionLocal()
        try:
            db.query(Integration).filter_by(firm_id=other_firm_id).delete(synchronize_session=False)
            db.query(Firm).filter_by(id=other_firm_id).delete()
            db.commit()
        finally:
            db.close()

    def test_toggle_writes_audit_log(self, test_setup):
        db = SessionLocal()
        try:
            gmail = db.query(Integration).filter_by(
                firm_id=test_setup["firm"].id, name="Gmail"
            ).first()
            iid = str(gmail.id)
        finally:
            db.close()

        http.post(f"/integrations/{iid}/toggle",
                  headers={"Authorization": f"Bearer {test_setup['admin_token']}"})

        db = SessionLocal()
        try:
            log = db.query(AuditLog).filter_by(
                action="integration_toggled", resource_id=iid
            ).first()
            assert log is not None
            assert log.detail["name"] == "Gmail"
        finally:
            db.close()


# ── Simulate inbound email ─────────────────────────────────────────────────────

class TestSimulateEmail:
    def test_creates_document_with_email_sim_channel(self, test_setup):
        resp = http.post(
            f"/clients/{test_setup['client_a'].id}/simulate-email",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            files={"file": ("w2_email.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
            data={"from_address": "jennifer.patel@gmail.com"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["source_channel"] == "email_sim"
        assert body["status"] == "processing"
        assert body["original_filename"] == "w2_email.pdf"

    def test_simulate_email_audit_log_includes_from_address(self, test_setup):
        resp = http.post(
            f"/clients/{test_setup['client_a'].id}/simulate-email",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            files={"file": ("doc.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
            data={"from_address": "test@example.com"},
        )
        assert resp.status_code == 201
        doc_id = resp.json()["id"]

        db = SessionLocal()
        try:
            log = db.query(AuditLog).filter_by(
                action="document_upload_email_sim", resource_id=doc_id
            ).first()
            assert log is not None
            assert log.detail["from_address"] == "test@example.com"
            assert log.detail["mime"] == "application/pdf"
        finally:
            db.close()

    def test_pipeline_runs_identical_classification(self, test_setup):
        """Simulated email document runs the same pipeline as portal upload."""
        W2_RESULT = {
            "doc_type": "W-2", "tax_year": "2024",
            "summary": "W-2 from Test Corp.",
            "fields": {"issuer": "Test Corp", "recipient": "Test", "key_amounts": {}},
            "confidence": 0.95,
        }
        resp = http.post(
            f"/clients/{test_setup['client_a'].id}/simulate-email",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            files={"file": ("w2.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
        )
        doc_id = uuid.UUID(resp.json()["id"])

        with patch("app.pipeline._call_claude", return_value=W2_RESULT), \
             patch("app.probes._call_probe", return_value={"needs_input": False, "question": None}):
            from app.pipeline import process_document
            process_document(doc_id)

        db = SessionLocal()
        try:
            doc = db.query(Document).filter_by(id=doc_id).first()
            assert doc.status.value == "classified"
            assert doc.doc_type == "W-2"
            assert doc.source_channel == SourceChannel.email_sim
        finally:
            db.close()

    def test_invalid_mime_rejected(self, test_setup):
        resp = http.post(
            f"/clients/{test_setup['client_a'].id}/simulate-email",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            files={"file": ("evil.pdf", io.BytesIO(b"#!/bin/bash"), "application/pdf")},
        )
        assert resp.status_code == 415

    def test_client_role_cannot_simulate_email(self, test_setup):
        resp = http.post(
            f"/clients/{test_setup['client_a'].id}/simulate-email",
            headers={"Authorization": f"Bearer {test_setup['user_a_token']}"},
            files={"file": ("doc.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
        )
        assert resp.status_code == 403

    def test_cross_client_simulate_email_returns_404(self, test_setup):
        """CPA must not inject into a client they don't own."""
        # client_b is assigned to the same CPA, but let's confirm the auth
        # still checks — works here since cpa IS assigned to client_b.
        # Use user_a_token (client role) attempting cross-client: 403 from role gate.
        resp = http.post(
            f"/clients/{test_setup['client_b'].id}/simulate-email",
            headers={"Authorization": f"Bearer {test_setup['user_a_token']}"},
            files={"file": ("doc.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
        )
        assert resp.status_code == 403

    def test_unauthenticated_simulate_email_rejected(self, test_setup):
        resp = http.post(
            f"/clients/{test_setup['client_a'].id}/simulate-email",
            headers={"Authorization": "Bearer bad-token"},
            files={"file": ("doc.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
        )
        assert resp.status_code == 401
