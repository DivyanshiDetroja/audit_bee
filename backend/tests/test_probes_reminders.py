"""
Integration tests for Phase 6: context-probes and AI-drafted reminders.

Claude calls are mocked so we don't hit the real API.
"""

import io
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import (
    ContextEntry,
    ContextProbe,
    ContextSource,
    ProbeStatus,
    Reminder,
    ReminderStatus,
)

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

W2_RESULT = {
    "doc_type": "W-2",
    "tax_year": "2024",
    "summary": "W-2 from Test Corp showing wages of $50,000 for tax year 2024.",
    "fields": {"issuer": "Test Corp", "recipient": "Test Client", "key_amounts": {}},
    "confidence": 0.97,
}

PROBE_NEEDS_INPUT = {
    "needs_input": True,
    "question": "The W-2 lists Test Corp — is this the client's only employer for 2024?",
}

PROBE_NO_INPUT = {"needs_input": False, "question": None}

DRAFT_EMAIL = {
    "subject": "Action Required: Outstanding Tax Documents",
    "body": "Dear Client A,\n\nWe still need a few documents to complete your return...",
}


def _seed(client_id, token):
    return http.post(
        f"/clients/{client_id}/checklist/seed",
        headers={"Authorization": f"Bearer {token}"},
    )


def _upload_and_classify(client_id, token, probe_result=PROBE_NO_INPUT):
    """Upload a PDF and run the pipeline with mocked Claude calls."""
    up = http.post(
        f"/clients/{client_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("w2.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
    )
    assert up.status_code == 201
    doc_id = uuid.UUID(up.json()["id"])

    with (
        patch("app.pipeline._call_claude", return_value=W2_RESULT),
        patch("app.probes._call_probe", return_value=probe_result),
    ):
        from app.pipeline import process_document
        process_document(doc_id)

    return doc_id


def _create_probe_directly(client_id) -> uuid.UUID:
    """Insert an open probe directly without going through the pipeline."""
    db = SessionLocal()
    try:
        probe = ContextProbe(
            client_id=client_id,
            question="Does the client have additional 1099s not yet provided?",
            status=ProbeStatus.open,
        )
        db.add(probe)
        db.commit()
        return probe.id
    finally:
        db.close()


# ── Context probe — pipeline ───────────────────────────────────────────────────

class TestProbeCreation:
    def test_probe_created_when_claude_flags_ambiguity(self, test_setup):
        _seed(test_setup["client_a"].id, test_setup["cpa_token"])
        _upload_and_classify(
            test_setup["client_a"].id,
            test_setup["cpa_token"],
            probe_result=PROBE_NEEDS_INPUT,
        )

        db = SessionLocal()
        try:
            probe = (
                db.query(ContextProbe)
                .filter_by(client_id=test_setup["client_a"].id, status=ProbeStatus.open)
                .first()
            )
            assert probe is not None
            assert "W-2" in probe.question or "employer" in probe.question
        finally:
            db.close()

    def test_probe_not_created_when_no_ambiguity(self, test_setup):
        _seed(test_setup["client_a"].id, test_setup["cpa_token"])
        _upload_and_classify(
            test_setup["client_a"].id,
            test_setup["cpa_token"],
            probe_result=PROBE_NO_INPUT,
        )

        db = SessionLocal()
        try:
            count = (
                db.query(ContextProbe)
                .filter_by(client_id=test_setup["client_a"].id)
                .count()
            )
            assert count == 0
        finally:
            db.close()

    def test_probe_not_created_when_claude_fails(self, test_setup):
        """Pipeline probe failure must be silent — document still classifies."""
        _seed(test_setup["client_a"].id, test_setup["cpa_token"])
        up = http.post(
            f"/clients/{test_setup['client_a'].id}/documents",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            files={"file": ("w2.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
        )
        doc_id = uuid.UUID(up.json()["id"])

        with (
            patch("app.pipeline._call_claude", return_value=W2_RESULT),
            patch("app.probes._call_probe", side_effect=Exception("network error")),
        ):
            from app.pipeline import process_document
            process_document(doc_id)

        db = SessionLocal()
        try:
            from app.models import Document, DocumentStatus
            doc = db.query(Document).filter_by(id=doc_id).first()
            assert doc.status == DocumentStatus.classified  # document still classified
            count = db.query(ContextProbe).filter_by(client_id=test_setup["client_a"].id).count()
            assert count == 0
        finally:
            db.close()


# ── Context probe — answer endpoint ───────────────────────────────────────────

class TestProbeAnswer:
    def test_answer_probe_marks_answered_and_creates_context_entry(self, test_setup):
        probe_id = _create_probe_directly(test_setup["client_a"].id)

        resp = http.post(
            f"/clients/{test_setup['client_a'].id}/probes/{probe_id}/answer",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            json={"answer": "No, only one employer for 2024."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "answered"
        assert data["answer"] == "No, only one employer for 2024."
        assert data["answered_by"] == str(test_setup["cpa"].id)

        db = SessionLocal()
        try:
            entry = (
                db.query(ContextEntry)
                .filter_by(
                    client_id=test_setup["client_a"].id,
                    source=ContextSource.probe_answer,
                )
                .first()
            )
            assert entry is not None
            assert "No, only one employer" in entry.content
        finally:
            db.close()

    def test_answer_probe_twice_returns_409(self, test_setup):
        probe_id = _create_probe_directly(test_setup["client_a"].id)
        payload = {"answer": "Only one employer."}

        http.post(
            f"/clients/{test_setup['client_a'].id}/probes/{probe_id}/answer",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            json=payload,
        )
        resp = http.post(
            f"/clients/{test_setup['client_a'].id}/probes/{probe_id}/answer",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            json=payload,
        )
        assert resp.status_code == 409

    def test_client_role_cannot_answer_probe(self, test_setup):
        probe_id = _create_probe_directly(test_setup["client_a"].id)
        resp = http.post(
            f"/clients/{test_setup['client_a'].id}/probes/{probe_id}/answer",
            headers={"Authorization": f"Bearer {test_setup['user_a_token']}"},
            json={"answer": "I think so."},
        )
        assert resp.status_code == 403

    def test_cross_client_probe_returns_404(self, test_setup):
        """CPA must not be able to answer a probe via the wrong client path."""
        probe_id = _create_probe_directly(test_setup["client_a"].id)
        resp = http.post(
            f"/clients/{test_setup['client_b'].id}/probes/{probe_id}/answer",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            json={"answer": "yes"},
        )
        assert resp.status_code == 404

    def test_list_probes_filtered_by_status(self, test_setup):
        _create_probe_directly(test_setup["client_a"].id)
        _create_probe_directly(test_setup["client_a"].id)

        resp = http.get(
            f"/clients/{test_setup['client_a'].id}/probes?status=open",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        assert all(p["status"] == "open" for p in resp.json())


# ── AI-drafted reminders ───────────────────────────────────────────────────────

class TestReminders:
    def test_draft_reminder_returns_draft_status(self, test_setup):
        _seed(test_setup["client_a"].id, test_setup["cpa_token"])

        with patch("app.reminders._call_reminder", return_value=DRAFT_EMAIL):
            resp = http.post(
                f"/clients/{test_setup['client_a'].id}/reminders/draft",
                headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "draft"
        assert data["draft_subject"] == DRAFT_EMAIL["subject"]
        assert data["draft_body"] == DRAFT_EMAIL["body"]
        assert data["sent_at"] is None

    def test_draft_reminder_with_no_pending_returns_422(self, test_setup):
        """Nothing to remind about when checklist is empty or fully received."""
        # No checklist seeded → no pending items
        with patch("app.reminders._call_reminder", return_value=DRAFT_EMAIL):
            resp = http.post(
                f"/clients/{test_setup['client_a'].id}/reminders/draft",
                headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            )
        assert resp.status_code == 422

    def test_client_role_cannot_draft_reminder(self, test_setup):
        resp = http.post(
            f"/clients/{test_setup['client_a'].id}/reminders/draft",
            headers={"Authorization": f"Bearer {test_setup['user_a_token']}"},
        )
        assert resp.status_code == 403

    def test_send_reminder_marks_sent_with_audit_log(self, test_setup):
        _seed(test_setup["client_a"].id, test_setup["cpa_token"])

        with patch("app.reminders._call_reminder", return_value=DRAFT_EMAIL):
            draft_resp = http.post(
                f"/clients/{test_setup['client_a'].id}/reminders/draft",
                headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            )
        reminder_id = draft_resp.json()["id"]

        send_resp = http.post(
            f"/clients/{test_setup['client_a'].id}/reminders/{reminder_id}/send",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            json={},
        )
        assert send_resp.status_code == 200
        data = send_resp.json()
        assert data["status"] == "sent"
        assert data["sent_at"] is not None

        db = SessionLocal()
        try:
            from app.models import AuditLog
            log = (
                db.query(AuditLog)
                .filter_by(
                    user_id=test_setup["cpa"].id,
                    action="reminder_sent",
                    resource_id=reminder_id,
                )
                .first()
            )
            assert log is not None
        finally:
            db.close()

    def test_send_allows_editing_subject_and_body(self, test_setup):
        _seed(test_setup["client_a"].id, test_setup["cpa_token"])

        with patch("app.reminders._call_reminder", return_value=DRAFT_EMAIL):
            draft_resp = http.post(
                f"/clients/{test_setup['client_a'].id}/reminders/draft",
                headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            )
        reminder_id = draft_resp.json()["id"]

        send_resp = http.post(
            f"/clients/{test_setup['client_a'].id}/reminders/{reminder_id}/send",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            json={"subject": "Updated subject", "body": "Edited body."},
        )
        assert send_resp.status_code == 200
        data = send_resp.json()
        assert data["draft_subject"] == "Updated subject"
        assert data["draft_body"] == "Edited body."

    def test_send_reminder_twice_returns_409(self, test_setup):
        _seed(test_setup["client_a"].id, test_setup["cpa_token"])

        with patch("app.reminders._call_reminder", return_value=DRAFT_EMAIL):
            draft_resp = http.post(
                f"/clients/{test_setup['client_a'].id}/reminders/draft",
                headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            )
        reminder_id = draft_resp.json()["id"]

        http.post(
            f"/clients/{test_setup['client_a'].id}/reminders/{reminder_id}/send",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            json={},
        )
        resp = http.post(
            f"/clients/{test_setup['client_a'].id}/reminders/{reminder_id}/send",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            json={},
        )
        assert resp.status_code == 409

    def test_cross_client_reminder_returns_404(self, test_setup):
        _seed(test_setup["client_a"].id, test_setup["cpa_token"])

        with patch("app.reminders._call_reminder", return_value=DRAFT_EMAIL):
            draft_resp = http.post(
                f"/clients/{test_setup['client_a'].id}/reminders/draft",
                headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            )
        reminder_id = draft_resp.json()["id"]

        resp = http.post(
            f"/clients/{test_setup['client_b'].id}/reminders/{reminder_id}/send",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            json={},
        )
        assert resp.status_code == 404
