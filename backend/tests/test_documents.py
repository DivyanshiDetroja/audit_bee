"""
Integration tests for document upload and download (Phase 3).

Tests run against the real docker-compose Postgres.  Each test gets a fresh
set of test data from the test_setup fixture and cleans up after itself.
"""

import io

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import AuditLog

http = TestClient(app)

# A syntactically valid 1-page PDF (tiny but real magic bytes)
MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"xref\n0 4\n"
    b"trailer<</Size 4/Root 1 0 R>>\n"
    b"startxref\n0\n%%EOF"
)


def _upload(client_id, token, content=MINIMAL_PDF, filename="test.pdf"):
    return http.post(
        f"/clients/{client_id}/documents",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": (filename, io.BytesIO(content), "application/pdf")},
    )


def _download(client_id, doc_id, token):
    return http.get(
        f"/clients/{client_id}/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {token}"},
    )


# ── Upload ─────────────────────────────────────────────────────────────────────

class TestUpload:
    def test_cpa_can_upload_to_assigned_client(self, test_setup):
        resp = _upload(test_setup["client_a"].id, test_setup["cpa_token"])
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "processing"
        assert body["mime_type"] == "application/pdf"
        assert body["storage_key"]  # opaque UUID, not the original filename

    def test_invalid_mime_type_rejected(self, test_setup):
        """Magic bytes are sniffed — a shell script must be rejected even with a .pdf name."""
        resp = http.post(
            f"/clients/{test_setup['client_a'].id}/documents",
            headers={"Authorization": f"Bearer {test_setup['cpa_token']}"},
            files={"file": ("evil.pdf", io.BytesIO(b"#!/bin/bash\nrm -rf /"), "application/pdf")},
        )
        assert resp.status_code == 415

    def test_unauthenticated_upload_rejected(self, test_setup):
        resp = _upload(test_setup["client_a"].id, "not-a-valid-token")
        assert resp.status_code == 401

    def test_upload_audit_log_written(self, test_setup):
        resp = _upload(test_setup["client_a"].id, test_setup["cpa_token"])
        assert resp.status_code == 201
        doc_id = resp.json()["id"]

        db = SessionLocal()
        try:
            log = db.query(AuditLog).filter_by(
                user_id=test_setup["cpa"].id,
                action="document_upload",
                resource_id=doc_id,
            ).first()
            assert log is not None
            assert log.detail["mime"] == "application/pdf"
        finally:
            db.close()


# ── Download ───────────────────────────────────────────────────────────────────

class TestDownload:
    def test_unauthorized_download_returns_404(self, test_setup):
        """
        Core no-leak test: user_a (client_a's user) must not be able to
        download a document that belongs to client_b.
        """
        # CPA uploads to client_b
        up = _upload(test_setup["client_b"].id, test_setup["cpa_token"])
        assert up.status_code == 201
        doc_id = up.json()["id"]

        # user_a tries to download via client_b's path → must be 404
        resp = _download(test_setup["client_b"].id, doc_id, test_setup["user_a_token"])
        assert resp.status_code == 404

    def test_authorized_download_returns_file_bytes(self, test_setup):
        """user_a can download their own document and gets the original bytes back."""
        up = _upload(test_setup["client_a"].id, test_setup["cpa_token"])
        assert up.status_code == 201
        doc_id = up.json()["id"]

        resp = _download(test_setup["client_a"].id, doc_id, test_setup["user_a_token"])
        assert resp.status_code == 200
        assert resp.content[:4] == b"%PDF"
        assert resp.headers["content-type"] == "application/pdf"

    def test_authorized_download_writes_audit_log(self, test_setup):
        """Every authorized download must produce an audit log row."""
        up = _upload(test_setup["client_a"].id, test_setup["cpa_token"])
        doc_id = up.json()["id"]

        _download(test_setup["client_a"].id, doc_id, test_setup["user_a_token"])

        db = SessionLocal()
        try:
            log = db.query(AuditLog).filter_by(
                user_id=test_setup["user_a"].id,
                action="document_download",
                resource_id=doc_id,
            ).first()
            assert log is not None
            assert log.resource_type == "document"
        finally:
            db.close()

    def test_idor_via_wrong_client_path_returns_404(self, test_setup):
        """
        IDOR test: even if the caller has access to client_b, they must not be
        able to reach client_a's document by substituting client_b's ID in the path.
        """
        # Upload to client_a
        up = _upload(test_setup["client_a"].id, test_setup["cpa_token"])
        assert up.status_code == 201
        doc_id = up.json()["id"]

        # CPA has access to both clients but uses client_b's path to reach client_a's doc
        resp = _download(test_setup["client_b"].id, doc_id, test_setup["cpa_token"])
        assert resp.status_code == 404

    def test_unauthenticated_download_rejected(self, test_setup):
        up = _upload(test_setup["client_a"].id, test_setup["cpa_token"])
        doc_id = up.json()["id"]

        resp = _download(test_setup["client_a"].id, doc_id, "bad-token")
        assert resp.status_code == 401
