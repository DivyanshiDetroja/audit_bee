"""
Integration tests for the Phase 5 checklist engine and context trail.

Tests run against the real docker-compose Postgres.  The pipeline is called
directly with a mocked Claude call so we don't hit the real API.
"""

import io
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import ContextEntry, RequiredDocument, RequiredDocStatus

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
    "fields": {
        "issuer": "Test Corp",
        "recipient": "Test Client",
        "key_amounts": {"wages": "$50,000", "federal_withheld": "$6,000"},
    },
    "confidence": 0.97,
}


def _seed(client_id, token):
    return http.post(
        f"/clients/{client_id}/checklist/seed",
        headers={"Authorization": f"Bearer {token}"},
    )


def _upload(client_id, token):
    return http.post(
        f"/clients/{client_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("w2.pdf", io.BytesIO(MINIMAL_PDF), "application/pdf")},
    )


# ── Seed endpoint ──────────────────────────────────────────────────────────────

class TestSeed:
    def test_seed_individual_creates_five_items(self, test_setup):
        resp = _seed(test_setup["client_a"].id, test_setup["cpa_token"])
        assert resp.status_code == 201
        items = resp.json()
        assert len(items) == 5
        doc_types = {item["doc_type"] for item in items}
        assert doc_types == {"W-2", "1099-INT", "1099-DIV", "1098", "prior_year_return"}
        assert all(item["status"] == "pending" for item in items)

    def test_seed_is_idempotent(self, test_setup):
        _seed(test_setup["client_a"].id, test_setup["cpa_token"])
        # Second call must return the same rows without creating duplicates.
        resp = _seed(test_setup["client_a"].id, test_setup["cpa_token"])
        assert resp.status_code == 201
        db = SessionLocal()
        try:
            count = (
                db.query(RequiredDocument)
                .filter_by(client_id=test_setup["client_a"].id)
                .count()
            )
            assert count == 5
        finally:
            db.close()

    def test_client_role_cannot_seed(self, test_setup):
        """Clients must not be able to seed their own checklist (role gate)."""
        resp = _seed(test_setup["client_a"].id, test_setup["user_a_token"])
        assert resp.status_code == 403

    def test_unauthenticated_seed_rejected(self, test_setup):
        resp = http.post(
            f"/clients/{test_setup['client_a'].id}/checklist/seed",
            headers={"Authorization": "Bearer bad-token"},
        )
        assert resp.status_code == 401


# ── Checklist / pending read endpoints ────────────────────────────────────────

class TestChecklistEndpoints:
    def test_get_checklist_returns_all_items(self, test_setup):
        _seed(test_setup["client_a"].id, test_setup["cpa_token"])
        resp = http.get(
            f"/clients/{test_setup['client_a'].id}/checklist",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 5

    def test_get_pending_returns_all_when_nothing_received(self, test_setup):
        _seed(test_setup["client_a"].id, test_setup["cpa_token"])
        resp = http.get(
            f"/clients/{test_setup['client_a'].id}/pending",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 5
        assert all(item["status"] == "pending" for item in resp.json())

    def test_get_context_empty_before_any_documents(self, test_setup):
        resp = http.get(
            f"/clients/{test_setup['client_a'].id}/context",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_cross_client_checklist_returns_404(self, test_setup):
        """user_a (client_a's portal user) must not see client_b's checklist."""
        _seed(test_setup["client_b"].id, test_setup["cpa_token"])
        resp = http.get(
            f"/clients/{test_setup['client_b'].id}/checklist",
            headers={"Authorization": f"Bearer {test_setup['user_a_token']}"},
        )
        assert resp.status_code == 404


# ── Pipeline checklist integration ────────────────────────────────────────────

class TestPipelineChecklist:
    def test_classification_flips_checklist_item_to_received(self, test_setup):
        _seed(test_setup["client_a"].id, test_setup["cpa_token"])

        up = _upload(test_setup["client_a"].id, test_setup["cpa_token"])
        assert up.status_code == 201
        doc_id = uuid.UUID(up.json()["id"])

        with patch("app.pipeline._call_claude", return_value=W2_RESULT):
            from app.pipeline import process_document
            process_document(doc_id)

        db = SessionLocal()
        try:
            w2 = (
                db.query(RequiredDocument)
                .filter_by(
                    client_id=test_setup["client_a"].id,
                    doc_type="W-2",
                )
                .first()
            )
            assert w2 is not None
            assert w2.status == RequiredDocStatus.received
            assert w2.satisfied_by_document_id == doc_id
        finally:
            db.close()

    def test_classification_creates_context_entry(self, test_setup):
        _seed(test_setup["client_a"].id, test_setup["cpa_token"])

        up = _upload(test_setup["client_a"].id, test_setup["cpa_token"])
        doc_id = uuid.UUID(up.json()["id"])

        with patch("app.pipeline._call_claude", return_value=W2_RESULT):
            from app.pipeline import process_document
            process_document(doc_id)

        db = SessionLocal()
        try:
            entries = (
                db.query(ContextEntry)
                .filter_by(client_id=test_setup["client_a"].id)
                .all()
            )
            assert len(entries) == 1
            assert "W-2" in entries[0].content
            assert entries[0].source.value == "document"
            assert entries[0].created_by == test_setup["cpa"].id
        finally:
            db.close()

    def test_pending_decreases_after_classification(self, test_setup):
        _seed(test_setup["client_a"].id, test_setup["cpa_token"])

        up = _upload(test_setup["client_a"].id, test_setup["cpa_token"])
        doc_id = uuid.UUID(up.json()["id"])

        with patch("app.pipeline._call_claude", return_value=W2_RESULT):
            from app.pipeline import process_document
            process_document(doc_id)

        resp = http.get(
            f"/clients/{test_setup['client_a'].id}/pending",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
        )
        assert resp.status_code == 200
        pending = resp.json()
        assert len(pending) == 4
        assert all(item["doc_type"] != "W-2" for item in pending)

    def test_context_trail_endpoint_shows_entry(self, test_setup):
        _seed(test_setup["client_a"].id, test_setup["cpa_token"])

        up = _upload(test_setup["client_a"].id, test_setup["cpa_token"])
        doc_id = uuid.UUID(up.json()["id"])

        with patch("app.pipeline._call_claude", return_value=W2_RESULT):
            from app.pipeline import process_document
            process_document(doc_id)

        resp = http.get(
            f"/clients/{test_setup['client_a'].id}/context",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
        )
        assert resp.status_code == 200
        entries = resp.json()
        assert len(entries) == 1
        assert "W-2" in entries[0]["content"]

    def test_needs_review_does_not_flip_checklist(self, test_setup):
        """Low-confidence classification must not touch the checklist."""
        _seed(test_setup["client_a"].id, test_setup["cpa_token"])

        up = _upload(test_setup["client_a"].id, test_setup["cpa_token"])
        doc_id = uuid.UUID(up.json()["id"])

        low_confidence = {**W2_RESULT, "doc_type": "other", "confidence": 0.3}
        with patch("app.pipeline._call_claude", return_value=low_confidence):
            from app.pipeline import process_document
            process_document(doc_id)

        db = SessionLocal()
        try:
            count = (
                db.query(RequiredDocument)
                .filter_by(
                    client_id=test_setup["client_a"].id,
                    status=RequiredDocStatus.pending,
                )
                .count()
            )
            assert count == 5  # nothing flipped

            ctx_count = (
                db.query(ContextEntry)
                .filter_by(client_id=test_setup["client_a"].id)
                .count()
            )
            assert ctx_count == 0  # no context entry for needs_review
        finally:
            db.close()
