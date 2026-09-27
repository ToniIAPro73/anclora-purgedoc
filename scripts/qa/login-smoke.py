#!/usr/bin/env python3
"""Sanitized production QA login smoke for PurgeDoc."""
from pathlib import Path
import os

import requests
from dotenv import dotenv_values


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    values = dotenv_values(os.environ.get("QA_ENV_FILE", root / "backend/.env.local"))
    email = os.environ.get("QA_USER_EMAIL") or values.get("QA_USER_EMAIL") or "qa2.purgedoc@anclora.local"
    password = os.environ.get("QA_USER_PASSWORD") or values.get("QA_USER_PASSWORD")
    base_url = os.environ.get("QA_BACKEND_URL") or values.get("QA_BACKEND_URL") or "https://api.purgedoc.anclora.com"
    if not password:
        print(f"QA identity: {email}")
        print("production backend: configured")
        print("login: FAIL")
        print("secret configured: NO")
        print("secret exposed: NO")
        return 2

    client = requests.Session()
    try:
        login = client.post(f"{base_url.rstrip('/')}/api/auth/login", json={"email": email, "password": password}, timeout=20)
        authenticated = client.get(f"{base_url.rstrip('/')}/api/auth/me", timeout=20) if login.status_code == 200 else None
        logout = client.post(f"{base_url.rstrip('/')}/api/auth/logout", timeout=20) if authenticated is not None and authenticated.status_code == 200 else None
        print(f"QA identity: {email}")
        print("production backend: configured")
        print(f"login: {'PASS' if login.status_code == 200 else 'FAIL'}")
        print(f"authenticated check: {'PASS' if authenticated is not None and authenticated.status_code == 200 else 'FAIL'}")
        print(f"logout/cleanup: {'PASS' if logout is not None and logout.status_code == 200 else 'FAIL'}")
        print("secret exposed: NO")
        return 0 if login.status_code == 200 and authenticated is not None and authenticated.status_code == 200 and logout is not None and logout.status_code == 200 else 2
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
