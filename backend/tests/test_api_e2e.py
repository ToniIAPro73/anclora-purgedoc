"""End-to-end HTTP tests against a running backend (local by default)."""
import os
import io
import time
import pytest
import requests

# Explicit REACT_APP_BACKEND_URL, otherwise the local backend. Never a remote fallback.
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://127.0.0.1:8001").rstrip("/")


from backend.tests.auth_helper import get_authenticated_session

@pytest.fixture(scope="module")
def session():
    return get_authenticated_session(BASE_URL)


@pytest.fixture(scope="module")
def session_id(session):
    for _ in range(5):
        try:
            r = session.post(f"{BASE_URL}/api/sessions", timeout=30)
            if r.status_code == 200:
                sid = r.json()["session_id"]
                yield sid
                session.delete(f"{BASE_URL}/api/sessions/{sid}", timeout=15)
                return
        except Exception:
            time.sleep(1)
    # Fallback attempt
    r = session.post(f"{BASE_URL}/api/sessions", timeout=30)
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]
    yield sid
    session.delete(f"{BASE_URL}/api/sessions/{sid}", timeout=15)


# --- Health & profiles ---
def test_health(session):
    for _ in range(5):
        try:
            r = session.get(f"{BASE_URL}/api/health", timeout=30)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(1)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "healthy"
    assert isinstance(data["profiles"], list)
    assert set(["rrhh", "legal", "soporte"]).issubset(set(data["profiles"]))
    assert data["product"] == "Anclora Purgedoc"


def test_profiles(session):
    r = session.get(f"{BASE_URL}/api/profiles", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, list)
    profile_ids = [p["id"] for p in data]
    assert "rrhh" in profile_ids
    assert "legal" in profile_ids
    assert "soporte" in profile_ids


# --- E2E flow for each fixture ---
@pytest.mark.parametrize("fixture_name,profile_id", [
    ("rrhh", "rrhh"),
    ("legal", "legal"),
    ("soporte", "soporte"),
])
def test_full_purge_pipeline(session, session_id, fixture_name, profile_id):
    # 1. Load synthetic fixture
    r = session.post(
        f"{BASE_URL}/api/fixtures/{fixture_name}/load",
        params={"session_id": session_id, "profile_id": profile_id},
        timeout=30,
    )
    assert r.status_code == 200, f"load failed: {r.text}"
    doc = r.json()
    doc_id = doc["id"]
    assert doc["status"] == "uploaded"
    assert doc["source_sha256"]
    assert doc["profile_id"] == profile_id

    # 2. Analyze document
    r = session.post(f"{BASE_URL}/api/documents/{doc_id}/analyze", timeout=60)
    assert r.status_code == 200, f"analyze failed: {r.text}"
    data = r.json()
    assert data["document"]["status"] == "ready_for_review"
    matches = data["matches"]
    assert len(matches) > 0, "No matches detected"

    # Verify no raw_text in public API response
    for m in matches:
        assert "raw_text" not in m, "Leak: raw_text returned in public API!"
        assert "original_text_hash" in m
        assert m["status"] == "pending"

    # 3. Accept first match, reject second (if exists)
    first_match_id = matches[0]["id"]
    r = session.patch(
        f"{BASE_URL}/api/matches/{first_match_id}",
        json={"status": "accepted"},
        timeout=15,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"

    # Test invalid status returns 400
    r_bad = session.patch(
        f"{BASE_URL}/api/matches/{first_match_id}",
        json={"status": "invalid_status"},
        timeout=15,
    )
    assert r_bad.status_code == 400

    # 4. Bulk accept remaining matches to test full redaction
    r = session.post(
        f"{BASE_URL}/api/documents/{doc_id}/matches/bulk",
        json={"all_visible": True, "status": "accepted"},
        timeout=15,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"

    # 5. Fetch page image for viewer
    r = session.get(f"{BASE_URL}/api/documents/{doc_id}/page-image/1", timeout=30)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert len(r.content) > 1000

    # 6. Purge and verify
    r = session.post(f"{BASE_URL}/api/documents/{doc_id}/purge", timeout=60)
    assert r.status_code == 200, f"purge failed: {r.text}"
    purge_res = r.json()
    assert purge_res["document_id"] == doc_id
    assert purge_res["verification_passed"] is True, f"Verification failed: {purge_res.get('failures')}"
    assert purge_res["status"] == "verified"
    assert purge_res["output_sha256"]
    assert purge_res["audit_id"]

    # 7. Download purged file
    r = session.get(f"{BASE_URL}/api/documents/{doc_id}/download", timeout=30)
    assert r.status_code == 200
    assert len(r.content) > 500

    # 8. Download audit JSON
    r = session.get(f"{BASE_URL}/api/documents/{doc_id}/audit.json", timeout=30)
    assert r.status_code == 200
    audit = r.json()
    assert audit["status"] == "verified"
    assert audit["summary"]["applied"] > 0
    # Guarantee: no raw text in audit
    audit_str = str(audit)
    assert "12345678Z" not in audit_str
    assert "87654321B" not in audit_str
    assert "sk_live_" not in audit_str

    # 9. Download audit PDF
    r = session.get(f"{BASE_URL}/api/documents/{doc_id}/audit.pdf", timeout=30)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert len(r.content) > 1000


# --- Negative / Edge Cases ---
def test_upload_unsupported_extension(session, session_id):
    fake_txt = io.BytesIO(b"Hello world")
    r = session.post(
        f"{BASE_URL}/api/sessions/{session_id}/documents",
        files={"file": ("test.txt", fake_txt, "text/plain")},
        data={"profile_id": "rrhh"},
        timeout=15,
    )
    assert r.status_code == 400


def test_unknown_document_matches(session):
    r = session.get(f"{BASE_URL}/api/documents/does-not-exist/matches", timeout=15)
    assert r.status_code == 404


def test_unknown_fixture(session, session_id):
    r = session.post(
        f"{BASE_URL}/api/fixtures/unknown/load",
        params={"session_id": session_id},
        timeout=15,
    )
    assert r.status_code == 404
