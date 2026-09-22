"""End-to-end HTTP tests hitting the public backend URL."""
import os
import io
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://audit-redact.preview.emergentagent.com").rstrip("/")

# Load public URL from frontend/.env if env not set
if not os.environ.get("REACT_APP_BACKEND_URL"):
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    return s


@pytest.fixture(scope="module")
def session_id(session):
    r = session.post(f"{BASE_URL}/api/sessions", timeout=30)
    assert r.status_code == 200, r.text
    sid = r.json()["session_id"]
    yield sid
    session.delete(f"{BASE_URL}/api/sessions/{sid}", timeout=15)


# --- Health & profiles ---
def test_health(session):
    r = session.get(f"{BASE_URL}/api/health", timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "healthy"
    assert isinstance(data["profiles"], list)
    assert set(["rrhh", "legal", "soporte"]).issubset(set(data["profiles"]))
    assert data["product"] == "Anclora Purgedoc"


def test_profiles(session):
    r = session.get(f"{BASE_URL}/api/profiles", timeout=30)
    assert r.status_code == 200
    profiles = r.json()
    assert len(profiles) >= 3
    ids = {p["id"] for p in profiles}
    assert {"rrhh", "legal", "soporte"}.issubset(ids)
    for p in profiles:
        assert "name_es" in p and "name_en" in p
        assert p["rules_count"] > 0


# --- Full pipelines through public API ---
@pytest.mark.parametrize("fixture_name,profile_id", [
    ("rrhh", "rrhh"),
    ("legal", "legal"),
    ("soporte", "soporte"),
])
def test_full_purge_pipeline(session, session_id, fixture_name, profile_id):
    # Load fixture
    r = session.post(
        f"{BASE_URL}/api/fixtures/{fixture_name}/load",
        params={"session_id": session_id, "profile_id": profile_id},
        timeout=60,
    )
    assert r.status_code == 200, r.text
    doc = r.json()
    doc_id = doc["id"]
    assert doc["profile_id"] == profile_id
    assert doc["status"] == "uploaded"
    assert doc["source_sha256"]

    # Analyze
    r = session.post(f"{BASE_URL}/api/documents/{doc_id}/analyze", timeout=120)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["matches_count"] > 0, f"No matches detected for {fixture_name}"
    matches = data["matches"]
    # Ensure no raw text leakage
    assert all("raw_text" not in m for m in matches)
    assert all("original_text_hash" in m for m in matches)

    # Get matches endpoint
    r = session.get(f"{BASE_URL}/api/documents/{doc_id}/matches", timeout=30)
    assert r.status_code == 200
    assert len(r.json()) == len(matches)

    # Single match PATCH
    first_id = matches[0]["id"]
    r = session.patch(f"{BASE_URL}/api/matches/{first_id}", json={"status": "rejected"}, timeout=15)
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"

    # Invalid status
    r = session.patch(f"{BASE_URL}/api/matches/{first_id}", json={"status": "bogus"}, timeout=15)
    assert r.status_code == 400

    # Bulk accept all
    r = session.post(
        f"{BASE_URL}/api/documents/{doc_id}/matches/bulk",
        json={"all_visible": True, "status": "accepted"},
        timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["updated"] == len(matches)
    assert body["status"] == "accepted"

    # Page image (only for PDF-supported preview)
    r = session.get(f"{BASE_URL}/api/documents/{doc_id}/page-image/1", timeout=60)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("image/png")
    assert len(r.content) > 500

    # Purge & verify
    r = session.post(f"{BASE_URL}/api/documents/{doc_id}/purge", timeout=180)
    assert r.status_code == 200, r.text
    purge = r.json()
    assert purge["verification_passed"] is True, f"Verification failed: {purge.get('failures')}"
    assert purge["status"] == "verified"
    assert purge["output_sha256"]
    assert purge["audit_id"]

    # Downloads
    r = session.get(f"{BASE_URL}/api/documents/{doc_id}/download", timeout=60)
    assert r.status_code == 200
    assert len(r.content) > 500

    r = session.get(f"{BASE_URL}/api/documents/{doc_id}/audit.json", timeout=30)
    assert r.status_code == 200
    audit = r.json()
    assert audit["status"] == "verified"
    assert audit["audit_id"] == purge["audit_id"]

    r = session.get(f"{BASE_URL}/api/documents/{doc_id}/audit.pdf", timeout=30)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert len(r.content) > 1000


# --- Negative cases ---
def test_upload_unsupported_extension(session, session_id):
    files = {"file": ("bad.txt", io.BytesIO(b"hello"), "text/plain")}
    r = session.post(
        f"{BASE_URL}/api/sessions/{session_id}/documents",
        files=files, data={"profile_id": "rrhh"}, timeout=30,
    )
    assert r.status_code == 400


def test_unknown_document_matches(session):
    r = session.get(f"{BASE_URL}/api/documents/does-not-exist/matches", timeout=15)
    assert r.status_code == 404


def test_unknown_fixture(session, session_id):
    r = session.post(
        f"{BASE_URL}/api/fixtures/unknown/load",
        params={"session_id": session_id}, timeout=15,
    )
    assert r.status_code == 404
