import os
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import jwt
from fastapi import HTTPException
from sqlalchemy.orm import Session
from backend.auth.models import AuthAuditEventRow

APP_ENV = os.environ.get("APP_ENV", "development").lower()
JWT_SECRET = os.environ.get("JWT_SECRET")
if not JWT_SECRET:
    if APP_ENV == "production":
        raise RuntimeError("JWT_SECRET is required when APP_ENV=production")
    # Stable fallback in memory for local dev/testing
    JWT_SECRET = secrets.token_urlsafe(32)

JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 7

AUTH_WHITELIST_TOKEN_TTL_HOURS = int(os.environ.get("AUTH_WHITELIST_TOKEN_TTL_HOURS", "72"))
AUTH_PASSWORD_MIN_LENGTH = int(os.environ.get("AUTH_PASSWORD_MIN_LENGTH", "12"))

COOKIE_SECURE = (APP_ENV == "production")
COOKIE_SAMESITE = "none" if COOKIE_SECURE else "lax"
COOKIE_PATH = "/"

def get_admin_emails() -> List[str]:
    raw = os.environ.get("AUTH_ADMIN_EMAILS", "")
    return [e.strip().lower() for e in raw.split(",") if e.strip()]

ph = PasswordHasher(
    time_cost=2,
    memory_cost=19456,
    parallelism=1,
    hash_len=32,
    salt_len=16
)

def hash_password(password: str) -> str:
    return ph.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False

def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()

def generate_raw_token() -> str:
    return secrets.token_urlsafe(32)

def record_audit_event(
    db: Session,
    event: str,
    email: Optional[str] = None,
    user_id: Optional[str] = None,
    metadata: Optional[dict] = None
) -> AuthAuditEventRow:
    audit_entry = AuthAuditEventRow(
        event=event,
        email=email.strip().lower() if email else None,
        user_id=user_id,
        metadata_json=metadata or {}
    )
    db.add(audit_entry)
    try:
        db.commit()
    except Exception:
        db.rollback()
    return audit_entry

def create_access_token(user_id: str, email: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email.strip().lower(),
        "type": "access",
        "exp": expires
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expires
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
