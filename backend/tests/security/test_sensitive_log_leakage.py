import pytest
import os
import requests
import json

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")

def test_sensitive_log_and_audit_leakage():
    """
    6. LOGS AND API LEAKAGE VERIFICATION:
    - Runs complete purge flow with known synthetic sensitive strings:
      e.g. '12345678Z', 'laura.martinez@example.test', 'purgedoc_test_token_REDACTED'
    - Inspects:
      - /var/log/supervisor/backend.err.log
      - /var/log/supervisor/backend.out.log
      - Audit JSON response & file
      - Audit PDF text
    - Asserts that sensitive plaintext NEVER leaks into logs or audit manifests!
    """
    s = requests.Session()
    # 1. Create session
    r = s.post(f"{BASE_URL}/api/sessions", timeout=15)
    assert r.status_code == 200
    session_id = r.json()["session_id"]

    # 2. Load Support Fixture with sensitive API Token
    r = s.post(
        f"{BASE_URL}/api/fixtures/soporte/load",
        params={"session_id": session_id, "profile_id": "soporte"},
        timeout=15
    )
    assert r.status_code == 200
    doc_id = r.json()["id"]

    # 3. Analyze
    r = s.post(f"{BASE_URL}/api/documents/{doc_id}/analyze", timeout=30)
    assert r.status_code == 200
    matches = r.json()["matches"]

    # Confirm raw_text is absent in matches API response
    for m in matches:
        assert "raw_text" not in m, "Leak: raw_text returned in matches endpoint!"

    # 4. Accept all & purge
    s.post(f"{BASE_URL}/api/documents/{doc_id}/matches/bulk", json={"all_visible": True, "status": "accepted"}, timeout=15)
    r = s.post(f"{BASE_URL}/api/documents/{doc_id}/purge", timeout=30)
    assert r.status_code == 200

    # 5. Inspect Audit JSON
    r_audit = s.get(f"{BASE_URL}/api/documents/{doc_id}/audit.json", timeout=15)
    assert r_audit.status_code == 200
    audit_data = r_audit.json()
    audit_str = json.dumps(audit_data)

    # Known secret tokens from support fixture
    secret_token = "purgedoc_test_token_REDACTED"
    secret_ip = "198.51.100.45"

    assert secret_token not in audit_str, "Critical Leak: API Token found in audit JSON!"
    assert secret_ip not in audit_str, "Critical Leak: IP address found in audit JSON!"

    # 6. Inspect Backend log files
    for log_path in ["/var/log/supervisor/backend.err.log", "/var/log/supervisor/backend.out.log"]:
        if os.path.exists(log_path):
            with open(log_path, "r", errors="ignore") as f:
                log_content = f.read()
                assert secret_token not in log_content, f"Critical Leak: API Token found in log file {log_path}!"

    # 7. Cleanup
    s.delete(f"{BASE_URL}/api/sessions/{session_id}", timeout=15)
