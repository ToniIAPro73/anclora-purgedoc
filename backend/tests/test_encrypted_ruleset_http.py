"""Live HTTP tests for encrypted ruleset export/preview endpoints via public preview URL."""
import os
import json
import base64
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://audit-redact.preview.emergentagent.com").rstrip("/")

SAMPLE_RULESET = {
    "ruleset_id": "http_test_alpha",
    "version": "1.0.0",
    "rules": [
        {
            "id": "rule_http_1",
            "name": "HTTP Project Code",
            "description": "sensitive project code",
            "entity_type": "PROJECT_CODE",
            "pattern": r"PRJ-[A-Z0-9]{5}",
            "case_sensitive": True,
            "confidence": 0.98,
            "priority": 60,
            "profiles": ["rrhh"],
            "enabled": True,
            "example": "PRJ-X892A"
        }
    ]
}


def _export(password="StrongPass_2026!", name="HTTP Test Ruleset", description="desc"):
    r = requests.post(f"{BASE_URL}/api/rules/export-encrypted", json={
        "ruleset": SAMPLE_RULESET,
        "password": password,
        "ruleset_name": name,
        "description": description
    }, timeout=30)
    return r


def test_export_envelope_schema_and_zero_pii():
    r = _export()
    assert r.status_code == 200, r.text
    env = r.json()
    assert env["format"] == "anclora-purgedoc-ruleset"
    assert env["format_version"] == 1
    assert env["crypto"]["cipher"] == "AES-256-GCM"
    assert env["crypto"]["kdf"] == "Argon2id"
    assert "salt" in env["crypto"]
    assert "nonce" in env["crypto"]
    assert "ciphertext" in env
    raw = json.dumps(env)
    for token in ["HTTP Project Code", "PRJ-[A-Z0-9]{5}", "PRJ-X892A",
                  "sensitive project code", "HTTP Test Ruleset"]:
        assert token not in raw, f"Plaintext leak: {token}"


def test_preview_correct_password():
    env = _export(password="Correct_Pw_123!").json()
    r = requests.post(f"{BASE_URL}/api/rules/preview-encrypted", json={
        "envelope": env, "password": "Correct_Pw_123!"
    }, timeout=30)
    assert r.status_code == 200, r.text
    prev = r.json()
    assert prev["rules_count"] == 1
    assert "canonical_hash" in prev


def test_preview_wrong_password_401():
    env = _export(password="Right_Pw_123!").json()
    r = requests.post(f"{BASE_URL}/api/rules/preview-encrypted", json={
        "envelope": env, "password": "WRONG!"
    }, timeout=30)
    assert r.status_code == 401
    body = r.json()
    assert body["detail"]["code"] == "ENCRYPTED_RULESET_AUTH_FAILED"


def test_preview_tampered_ciphertext_401():
    env = _export(password="Pw_123!").json()
    ct = bytearray(base64.b64decode(env["ciphertext"]))
    ct[10] ^= 0xFF
    env["ciphertext"] = base64.b64encode(ct).decode("ascii")
    r = requests.post(f"{BASE_URL}/api/rules/preview-encrypted", json={
        "envelope": env, "password": "Pw_123!"
    }, timeout=30)
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "ENCRYPTED_RULESET_AUTH_FAILED"


def test_preview_tampered_aad_metadata_401():
    env = _export(password="Pw_123!").json()
    env["crypto"]["time_cost"] = 4
    r = requests.post(f"{BASE_URL}/api/rules/preview-encrypted", json={
        "envelope": env, "password": "Pw_123!"
    }, timeout=30)
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "ENCRYPTED_RULESET_AUTH_FAILED"
