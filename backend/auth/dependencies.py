from typing import Optional
from fastapi import Request, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.auth.database import get_db
from backend.auth.models import UserRow, AuthWhitelistRow, SessionOwnerRow
from backend.auth.security import decode_token, get_admin_emails
from backend.services.sessions import session_store
from backend.db.models import SessionRow, DocumentRow, BatchRow

security_bearer = HTTPBearer(auto_error=False)


def get_current_user_optional(
    request: Request,
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> Optional[UserRow]:
    # 1. Check HttpOnly cookie
    token = request.cookies.get("access_token")

    # 2. Check Bearer Authorization header
    if not token and auth:
        token = auth.credentials

    # 3. Check query param (for EventSource SSE if cookie was omitted)
    if not token and "token" in request.query_params:
        token = request.query_params["token"]

    if not token:
        return None

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None

        user = db.query(UserRow).filter(UserRow.id == user_id).first()
        if not user or user.status != "active":
            return None

        # Re-check active whitelist admission for immediate revocation guarantee
        whitelist = db.query(AuthWhitelistRow).filter(
            (AuthWhitelistRow.user_id == user.id) | (AuthWhitelistRow.email == user.email.lower())
        ).first()
        if not whitelist or whitelist.status != "active":
            return None

        return user
    except Exception:
        return None


def get_current_user_required(
    current_user: Optional[UserRow] = Depends(get_current_user_optional)
) -> UserRow:
    if not current_user:
        raise HTTPException(status_code=401, detail="Autenticación requerida para esta acción.")
    return current_user


def get_current_admin_user(
    current_user: UserRow = Depends(get_current_user_required)
) -> UserRow:
    admin_emails = get_admin_emails()
    if not admin_emails or current_user.email.strip().lower() not in admin_emails:
        raise HTTPException(status_code=403, detail="Acceso restringido a administradores.")
    return current_user


# ----------------- Object-Level Ownership Guards -----------------

def verify_session_ownership(session_id: str, user_id: str, db: Session) -> bool:
    # Check in-memory session store
    sess = session_store.sessions.get(session_id)
    if sess:
        sess_user = sess.get("user_id")
        if sess_user is not None:
            return sess_user == user_id
    # Check database session ownership
    owner = db.query(SessionOwnerRow).filter(SessionOwnerRow.session_id == session_id).first()
    if owner:
        return owner.user_id == user_id
    return False


def verify_document_ownership(doc_id: str, user_id: str, db: Session) -> bool:
    # Check in-memory document store
    doc = session_store.documents.get(doc_id)
    if doc:
        return verify_session_ownership(doc.session_id, user_id, db)
    # Check database document
    doc_row = db.query(DocumentRow).filter(DocumentRow.id == doc_id).first()
    if doc_row:
        return verify_session_ownership(doc_row.session_id, user_id, db)
    return False


def verify_batch_ownership(batch_id: str, user_id: str, db: Session) -> bool:
    # Check in-memory batch store
    batch = session_store.batches.get(batch_id)
    if batch:
        return verify_session_ownership(batch.session_id, user_id, db)
    # Check database batch
    batch_row = db.query(BatchRow).filter(BatchRow.id == batch_id).first()
    if batch_row:
        return verify_session_ownership(batch_row.session_id, user_id, db)
    return False


def verify_match_ownership(match_id: str, user_id: str, db: Session) -> bool:
    for doc_id, matches_dict in session_store.matches.items():
        if match_id in matches_dict:
            return verify_document_ownership(doc_id, user_id, db)
    return False


def require_owned_session(
    session_id: str,
    current_user: UserRow = Depends(get_current_user_required),
    db: Session = Depends(get_db)
) -> str:
    if not verify_session_ownership(session_id, current_user.id, db):
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")
    return session_id


def require_owned_document(
    doc_id: str,
    current_user: UserRow = Depends(get_current_user_required),
    db: Session = Depends(get_db)
) -> str:
    if not verify_document_ownership(doc_id, current_user.id, db):
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    return doc_id


def require_owned_batch(
    batch_id: str,
    current_user: UserRow = Depends(get_current_user_required),
    db: Session = Depends(get_db)
) -> str:
    if not verify_batch_ownership(batch_id, current_user.id, db):
        raise HTTPException(status_code=404, detail="Lote no encontrado.")
    return batch_id


def require_owned_match(
    match_id: str,
    current_user: UserRow = Depends(get_current_user_required),
    db: Session = Depends(get_db)
) -> str:
    if not verify_match_ownership(match_id, current_user.id, db):
        raise HTTPException(status_code=404, detail="Coincidencia no encontrada.")
    return match_id
