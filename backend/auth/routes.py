import os
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Response, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.auth.database import get_db
from backend.auth.models import UserRow, AuthWhitelistRow
from backend.auth.security import (
    hash_password, verify_password, create_access_token, create_refresh_token,
    hash_token, generate_raw_token, record_audit_event,
    AUTH_WHITELIST_TOKEN_TTL_HOURS, AUTH_PASSWORD_MIN_LENGTH,
    COOKIE_SECURE, COOKIE_SAMESITE, COOKIE_PATH
)
from backend.auth.dependencies import (
    get_current_user_optional, get_current_user_required, get_current_admin_user
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class ActivateRequest(BaseModel):
    token: str
    password: str
    display_name: Optional[str] = None


class WhitelistCreateRequest(BaseModel):
    email: str


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str]
    created_at: datetime


def is_token_expired(expires_at: Optional[datetime]) -> bool:
    if not expires_at:
        return False
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        return expires_at.replace(tzinfo=timezone.utc) < now
    return expires_at < now


@router.get("/activation/validate")
def validate_activation_token(token: str, db: Session = Depends(get_db)):
    if not token or not token.strip():
        raise HTTPException(status_code=400, detail="Token no proporcionado.")

    t_hash = hash_token(token)
    entry = db.query(AuthWhitelistRow).filter(
        AuthWhitelistRow.token_hash == t_hash,
        AuthWhitelistRow.status == "pending"
    ).first()

    if not entry or is_token_expired(entry.expires_at):
        record_audit_event(
            db, "activation_rejected",
            email=entry.email if entry else None,
            metadata={"reason": "invalid_or_expired_token"}
        )
        raise HTTPException(status_code=400, detail="Invitación no válida, expirada o ya utilizada.")

    return {
        "valid": True,
        "email": entry.email
    }


@router.post("/activate", response_model=UserResponse)
def activate_account(req: ActivateRequest, response: Response, db: Session = Depends(get_db)):
    if len(req.password) < AUTH_PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"La contraseña debe tener al menos {AUTH_PASSWORD_MIN_LENGTH} caracteres."
        )

    t_hash = hash_token(req.token)
    entry = db.query(AuthWhitelistRow).filter(
        AuthWhitelistRow.token_hash == t_hash,
        AuthWhitelistRow.status == "pending"
    ).first()

    now = datetime.now(timezone.utc)
    if not entry or is_token_expired(entry.expires_at):
        record_audit_event(
            db, "activation_rejected",
            email=entry.email if entry else None,
            metadata={"reason": "invalid_or_expired_token"}
        )
        raise HTTPException(status_code=400, detail="Invitación no válida, expirada o ya utilizada.")

    clean_email = entry.email.strip().lower()
    existing_user = db.query(UserRow).filter(UserRow.email == clean_email).first()
    if existing_user:
        record_audit_event(
            db, "activation_rejected",
            email=clean_email,
            user_id=existing_user.id,
            metadata={"reason": "user_already_exists"}
        )
        raise HTTPException(status_code=400, detail="El usuario ya se encuentra registrado.")

    # Atomic creation of user and activation of whitelist
    hashed = hash_password(req.password)
    user = UserRow(
        email=clean_email,
        password_hash=hashed,
        display_name=req.display_name or clean_email.split("@")[0],
        status="active"
    )
    db.add(user)
    db.flush()

    entry.status = "active"
    entry.user_id = user.id
    entry.activated_at = now
    entry.token_hash = None
    entry.updated_at = now

    record_audit_event(db, "activation_succeeded", email=clean_email, user_id=user.id)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=3600,
        path=COOKIE_PATH
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=604800,
        path=COOKIE_PATH
    )

    return user


@router.post("/register")
def register():
    raise HTTPException(
        status_code=403,
        detail="El registro público está deshabilitado. Se requiere una invitación de acceso para PurgeDoc."
    )


@router.post("/login", response_model=UserResponse)
def login(req: LoginRequest, response: Response, db: Session = Depends(get_db)):
    clean_email = req.email.strip().lower()
    generic_err = "Credenciales incorrectas."

    user = db.query(UserRow).filter(UserRow.email == clean_email).first()
    if not user or not verify_password(req.password, user.password_hash):
        record_audit_event(db, "login_failed", email=clean_email, metadata={"reason": "invalid_credentials"})
        raise HTTPException(status_code=401, detail=generic_err)

    if user.status != "active":
        record_audit_event(db, "login_rejected_disabled", email=clean_email, user_id=user.id)
        raise HTTPException(status_code=401, detail=generic_err)

    # Verify active whitelist admission
    whitelist = db.query(AuthWhitelistRow).filter(
        (AuthWhitelistRow.user_id == user.id) | (AuthWhitelistRow.email == clean_email)
    ).first()
    if not whitelist or whitelist.status != "active":
        record_audit_event(db, "login_failed", email=clean_email, user_id=user.id, metadata={"reason": "whitelist_not_active"})
        raise HTTPException(status_code=401, detail=generic_err)

    access_token = create_access_token(user.id, user.email)
    refresh_token = create_refresh_token(user.id)

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=3600,
        path=COOKIE_PATH
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=604800,
        path=COOKIE_PATH
    )

    record_audit_event(db, "login_succeeded", email=user.email, user_id=user.id)
    return user


@router.get("/me")
def get_me(user: Optional[UserRow] = Depends(get_current_user_optional)):
    if not user:
        return {"authenticated": False, "user": None}
    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name
        }
    }


@router.post("/logout")
def logout(response: Response, user: Optional[UserRow] = Depends(get_current_user_optional), db: Session = Depends(get_db)):
    if user:
        record_audit_event(db, "logout", email=user.email, user_id=user.id)
    response.delete_cookie(key="access_token", path=COOKIE_PATH, httponly=True, secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)
    response.delete_cookie(key="refresh_token", path=COOKIE_PATH, httponly=True, secure=COOKIE_SECURE, samesite=COOKIE_SAMESITE)
    return {"message": "Sesión cerrada correctamente."}


# --- Operator / Admin Whitelist Management ---

@router.post("/whitelist")
def add_to_whitelist(
    req: WhitelistCreateRequest,
    admin: UserRow = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    clean_email = req.email.strip().lower()
    if not clean_email or "@" not in clean_email:
        raise HTTPException(status_code=400, detail="Correo electrónico inválido.")

    existing = db.query(AuthWhitelistRow).filter(AuthWhitelistRow.email == clean_email).first()
    if existing and existing.status == "active":
        raise HTTPException(status_code=400, detail="El correo ya se encuentra en la whitelist con acceso activo.")

    raw_token = generate_raw_token()
    t_hash = hash_token(raw_token)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=AUTH_WHITELIST_TOKEN_TTL_HOURS)

    if existing:
        existing.status = "pending"
        existing.token_hash = t_hash
        existing.expires_at = expires_at
        existing.updated_at = now
        entry = existing
    else:
        entry = AuthWhitelistRow(
            email=clean_email,
            status="pending",
            token_hash=t_hash,
            expires_at=expires_at,
            created_by=admin.email,
            created_at=now,
            updated_at=now
        )
        db.add(entry)

    record_audit_event(
        db, "whitelist_added",
        email=clean_email,
        user_id=admin.id,
        metadata={"created_by": admin.email, "expires_at": expires_at.isoformat()}
    )
    db.commit()
    db.refresh(entry)

    # Deliver raw activation token ONCE to the administrator
    return {
        "id": entry.id,
        "email": entry.email,
        "status": entry.status,
        "expires_at": entry.expires_at,
        "activation_token": raw_token
    }


@router.get("/whitelist")
def list_whitelist(
    admin: UserRow = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    entries = db.query(AuthWhitelistRow).order_by(AuthWhitelistRow.created_at.desc()).all()
    # Explicitly do NOT expose token_hash, passwords, or secrets
    return [
        {
            "id": e.id,
            "email": e.email,
            "status": e.status,
            "expires_at": e.expires_at,
            "activated_at": e.activated_at,
            "revoked_at": e.revoked_at,
            "user_id": e.user_id,
            "created_by": e.created_by,
            "created_at": e.created_at,
            "updated_at": e.updated_at
        }
        for e in entries
    ]


@router.post("/whitelist/{id}/rotate-token")
def rotate_whitelist_token(
    id: str,
    admin: UserRow = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    entry = db.query(AuthWhitelistRow).filter(AuthWhitelistRow.id == id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entrada de whitelist no encontrada.")

    raw_token = generate_raw_token()
    now = datetime.now(timezone.utc)
    entry.token_hash = hash_token(raw_token)
    entry.expires_at = now + timedelta(hours=AUTH_WHITELIST_TOKEN_TTL_HOURS)
    entry.status = "pending"
    entry.updated_at = now

    record_audit_event(
        db, "whitelist_token_rotated",
        email=entry.email,
        user_id=admin.id,
        metadata={"rotated_by": admin.email}
    )
    db.commit()
    db.refresh(entry)

    return {
        "id": entry.id,
        "email": entry.email,
        "status": entry.status,
        "expires_at": entry.expires_at,
        "activation_token": raw_token
    }


@router.post("/whitelist/{id}/revoke")
def revoke_whitelist_entry(
    id: str,
    admin: UserRow = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    entry = db.query(AuthWhitelistRow).filter(AuthWhitelistRow.id == id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entrada de whitelist no encontrada.")

    now = datetime.now(timezone.utc)
    entry.status = "revoked"
    entry.token_hash = None
    entry.revoked_at = now
    entry.updated_at = now

    # Also disable linked user account immediately to terminate active session access
    if entry.user_id:
        user = db.query(UserRow).filter(UserRow.id == entry.user_id).first()
        if user:
            user.status = "disabled"

    record_audit_event(
        db, "whitelist_revoked",
        email=entry.email,
        user_id=admin.id,
        metadata={"revoked_by": admin.email, "linked_user_id": entry.user_id}
    )
    db.commit()

    return {
        "message": "Acceso revocado correctamente.",
        "id": entry.id,
        "status": "revoked"
    }
