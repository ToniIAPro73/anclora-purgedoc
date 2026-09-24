import pytest
from fastapi.testclient import TestClient
from backend.server import app

@pytest.fixture
def client():
    return TestClient(app)

def test_anonymous_sessions_create_denied(client):
    r = client.post("/api/sessions")
    assert r.status_code == 401

def test_anonymous_profiles_denied(client):
    r = client.get("/api/profiles")
    assert r.status_code == 401

def test_anonymous_rules_validate_denied(client):
    r = client.post("/api/rules/validate", json={"pattern": "[0-9]+"})
    assert r.status_code == 401

def test_anonymous_document_upload_denied(client):
    r = client.post("/api/sessions/fake-session/documents", files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")})
    assert r.status_code == 401

def test_anonymous_document_analyze_denied(client):
    r = client.post("/api/documents/fake-doc/analyze")
    assert r.status_code == 401

def test_anonymous_matches_get_denied(client):
    r = client.get("/api/documents/fake-doc/matches")
    assert r.status_code == 401

def test_anonymous_match_update_denied(client):
    r = client.patch("/api/matches/fake-match", json={"status": "accepted"})
    assert r.status_code == 401

def test_anonymous_page_image_denied(client):
    r = client.get("/api/documents/fake-doc/page-image/1")
    assert r.status_code == 401

def test_anonymous_purge_denied(client):
    r = client.post("/api/documents/fake-doc/purge")
    assert r.status_code == 401

def test_anonymous_download_denied(client):
    r = client.get("/api/documents/fake-doc/download")
    assert r.status_code == 401

def test_anonymous_audit_json_denied(client):
    r = client.get("/api/documents/fake-doc/audit.json")
    assert r.status_code == 401

def test_anonymous_audit_pdf_denied(client):
    r = client.get("/api/documents/fake-doc/audit.pdf")
    assert r.status_code == 401

def test_anonymous_batch_config_denied(client):
    r = client.get("/api/batch/config")
    assert r.status_code == 401

def test_anonymous_batch_create_denied(client):
    r = client.post("/api/sessions/fake-session/batches", json={})
    assert r.status_code == 401

def test_anonymous_batch_get_denied(client):
    r = client.get("/api/batches/fake-batch")
    assert r.status_code == 401

def test_anonymous_batch_sse_denied(client):
    r = client.get("/api/batches/fake-batch/events")
    assert r.status_code == 401
