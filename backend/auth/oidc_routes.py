"""Anclora Identity OIDC login/callback for PurgeDoc.

This is an additional login path alongside the existing whitelist/password
flow in backend/auth/routes.py, gated behind ANCLORA_IDENTITY_ENABLED
(backend/auth/oidc.py). It never auto-provisions a PurgeDoc account: a
successful Anclora Identity login is only accepted for an email that already
has an active PurgeDoc `users` row and an active `auth_whitelist` entry —
exactly the same admission check `POST /auth/login` performs today. This
preserves PurgeDoc's closed-access invariant (docs/auth-access.md) instead of
turning the central IdP into a side door around it.

Authlib's `authorize_access_token()` + `parse_id_token()` perform the
Authorization Code + PKCE exchange and validate the ID token's issuer,
audience, signature (via the provider's published JWKS) and expiration; we
additionally check the `nonce` explicitly (Authlib requires it be passed
back) and `email_verified`.
"""
import secrets
from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from fastapi import Depends

from backend.auth.database import get_db
from backend.auth.models import UserRow, AuthWhitelistRow
from backend.auth.security import (
    create_access_token, create_refresh_token, record_audit_event,
    COOKIE_SECURE, COOKIE_SAMESITE, COOKIE_PATH
)
from backend.auth import oidc

router = APIRouter(prefix="/auth/anclora-identity", tags=["auth", "anclora-identity"])


def _require_enabled():
    if not oidc.ANCLORA_IDENTITY_ENABLED:
        raise HTTPException(status_code=404)


def _set_session_cookies(response: RedirectResponse, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        key="access_token", value=access_token, httponly=True,
        secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE, max_age=3600, path=COOKIE_PATH,
    )
    response.set_cookie(
        key="refresh_token", value=refresh_token, httponly=True,
        secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE, max_age=604800, path=COOKIE_PATH,
    )


@router.get("/login")
async def anclora_identity_login(request: Request):
    _require_enabled()
    nonce = secrets.token_urlsafe(32)
    request.session["anclora_identity_nonce"] = nonce
    return await oidc.oauth.anclora_identity.authorize_redirect(
        request, oidc.ANCLORA_IDENTITY_REDIRECT_URI, nonce=nonce
    )


@router.get("/callback")
async def anclora_identity_callback(request: Request, db: Session = Depends(get_db)):
    _require_enabled()

    try:
        token = await oidc.oauth.anclora_identity.authorize_access_token(request)
    except OAuthError:
        raise HTTPException(status_code=400, detail="OIDC_EXCHANGE_FAILED")

    nonce = request.session.pop("anclora_identity_nonce", None)
    try:
        claims = await oidc.oauth.anclora_identity.parse_id_token(request, token, nonce=nonce)
    except Exception:
        raise HTTPException(status_code=400, detail="OIDC_ID_TOKEN_INVALID")

    email = (claims.get("email") or "").strip().lower()
    if not email or not claims.get("email_verified"):
        record_audit_event(db, "oidc_login_rejected", email=email or None, metadata={"reason": "email_not_verified"})
        raise HTTPException(status_code=403, detail="EMAIL_NOT_VERIFIED")

    identity_sub = claims.get("sub")
    if not identity_sub:
        raise HTTPException(status_code=400, detail="OIDC_ID_TOKEN_INVALID")

    user = db.query(UserRow).filter(UserRow.email == email).first()
    if user is None:
        # No pre-existing whitelist-provisioned account: never auto-create
        # one from an OIDC login. PurgeDoc stays closed-access.
        record_audit_event(db, "oidc_login_rejected", email=email, metadata={"reason": "no_local_account"})
        raise HTTPException(status_code=403, detail="ACCESS_DENIED")

    whitelist = db.query(AuthWhitelistRow).filter(
        (AuthWhitelistRow.user_id == user.id) | (AuthWhitelistRow.email == email)
    ).first()
    if user.status != "active" or not whitelist or whitelist.status != "active":
        record_audit_event(db, "oidc_login_rejected", email=email, user_id=user.id, metadata={"reason": "whitelist_not_active"})
        raise HTTPException(status_code=403, detail="ACCESS_DENIED")

    if user.identity_sub is None:
        user.identity_sub = identity_sub
        db.commit()
    elif user.identity_sub != identity_sub:
        # A different Identity subject than the one previously linked to this
        # email must never be silently re-linked (account-takeover surface).
        record_audit_event(db, "oidc_login_rejected", email=email, user_id=user.id, metadata={"reason": "identity_subject_mismatch"})
        raise HTTPException(status_code=409, detail="IDENTITY_SUBJECT_MISMATCH")

    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id)

    response = RedirectResponse(url=oidc.ANCLORA_IDENTITY_POST_LOGIN_REDIRECT)
    _set_session_cookies(response, access_token, refresh_token)
    record_audit_event(db, "login_succeeded", email=user.email, user_id=user.id, metadata={"method": "anclora_identity"})
    return response
