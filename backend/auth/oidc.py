"""Anclora Identity OIDC relying-party client configuration for PurgeDoc.

Fail-closed feature flag: when ANCLORA_IDENTITY_ENABLED is unset or not
"true", the client is never registered and the routes in oidc_routes.py
return 404. Existing whitelist/password login (backend/auth/routes.py) is
completely unaffected either way — this is an additional login path, not a
replacement, until Toni explicitly decides otherwise.
"""
import os
from authlib.integrations.starlette_client import OAuth

ANCLORA_IDENTITY_ENABLED = os.environ.get("ANCLORA_IDENTITY_ENABLED", "false").strip().lower() == "true"
ANCLORA_IDENTITY_ISSUER_URL = os.environ.get("ANCLORA_IDENTITY_ISSUER_URL", "").rstrip("/")
ANCLORA_IDENTITY_CLIENT_ID = os.environ.get("ANCLORA_IDENTITY_CLIENT_ID", "purgedoc")
ANCLORA_IDENTITY_CLIENT_SECRET = os.environ.get("ANCLORA_IDENTITY_CLIENT_SECRET", "")
ANCLORA_IDENTITY_REDIRECT_URI = os.environ.get("ANCLORA_IDENTITY_REDIRECT_URI", "")
ANCLORA_IDENTITY_POST_LOGIN_REDIRECT = os.environ.get("ANCLORA_IDENTITY_POST_LOGIN_REDIRECT", "/app")

oauth = OAuth()

if ANCLORA_IDENTITY_ENABLED:
    if not ANCLORA_IDENTITY_ISSUER_URL or not ANCLORA_IDENTITY_CLIENT_SECRET or not ANCLORA_IDENTITY_REDIRECT_URI:
        raise RuntimeError(
            "ANCLORA_IDENTITY_ENABLED=true requires ANCLORA_IDENTITY_ISSUER_URL, "
            "ANCLORA_IDENTITY_CLIENT_SECRET and ANCLORA_IDENTITY_REDIRECT_URI to be set."
        )
    oauth.register(
        name="anclora_identity",
        client_id=ANCLORA_IDENTITY_CLIENT_ID,
        client_secret=ANCLORA_IDENTITY_CLIENT_SECRET,
        server_metadata_url=f"{ANCLORA_IDENTITY_ISSUER_URL}/.well-known/openid-configuration",
        client_kwargs={"scope": "openid profile email anclora_platform"},
    )
