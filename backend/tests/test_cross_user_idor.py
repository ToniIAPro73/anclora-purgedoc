import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from backend.server import app
from backend.auth.database import SessionLocal
from backend.auth.models import UserRow, AuthWhitelistRow
from backend.auth.security import hash_password, create_access_token
from backend.services.sessions import session_store
from backend.models import DocumentMetadata, BatchMetadata, MatchItem

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_active_user(db, email, password="UserPassword123!"):
    user = db.query(UserRow).filter(UserRow.email == email).first()
    if not user:
        user = UserRow(
            id=str(uuid.uuid4()),
            email=email,
            password_hash=hash_password(password),
            display_name=email.split("@")[0],
            status="active"
        )
        db.add(user)
        db.flush()

    wl = db.query(AuthWhitelistRow).filter(AuthWhitelistRow.email == email).first()
    if not wl:
        wl = AuthWhitelistRow(
            id=str(uuid.uuid4()),
            email=email,
            status="active",
            user_id=user.id,
            created_by="test_setup",
            activated_at=datetime.now(timezone.utc)
        )
        db.add(wl)
    else:
        wl.user_id = user.id
        wl.status = "active"
    db.commit()
    db.refresh(user)
    return user

def user_client(user):
    token = create_access_token(user.id, user.email)
    client = TestClient(app)
    client.cookies.set("access_token", token)
    return client

def test_cross_user_isolation(db_session):
    user_a = create_active_user(db_session, f"usera_{uuid.uuid4().hex[:6]}@anclora.local")
    user_b = create_active_user(db_session, f"userb_{uuid.uuid4().hex[:6]}@anclora.local")

    client_a = user_client(user_a)
    client_b = user_client(user_b)

    # User A creates a session
    res_a = client_a.post("/api/sessions")
    assert res_a.status_code == 200
    session_a_id = res_a.json()["session_id"]

    # User B attempts to access User A session expiry -> 404 (IDOR prevented)
    res_b_exp = client_b.get(f"/api/sessions/{session_a_id}/expiry")
    assert res_b_exp.status_code == 404

    # User B attempts to delete User A session -> 404
    res_b_del = client_b.delete(f"/api/sessions/{session_a_id}")
    assert res_b_del.status_code == 404

    # User B attempts to upload into User A session -> 404
    res_b_upl = client_b.post(
        f"/api/sessions/{session_a_id}/documents",
        files={"file": ("test.pdf", b"%PDF-1.4 sample", "application/pdf")}
    )
    assert res_b_upl.status_code == 404

    # User A creates batch under Session A
    batch_res = client_a.post(f"/api/sessions/{session_a_id}/batches", json={})
    assert batch_res.status_code == 200
    batch_a_id = batch_res.json()["id"]

    # User B attempts to get User A batch -> 404
    res_b_batch = client_b.get(f"/api/batches/{batch_a_id}")
    assert res_b_batch.status_code == 404

    # User B attempts to subscribe to User A batch events -> 404
    res_b_sse = client_b.get(f"/api/batches/{batch_a_id}/events")
    assert res_b_sse.status_code == 404

    # User B attempts to delete User A batch -> 404
    res_b_bdel = client_b.delete(f"/api/batches/{batch_a_id}")
    assert res_b_bdel.status_code == 404

    # User B attempts to cancel User A batch -> 404
    res_b_bcancel = client_b.post(f"/api/batches/{batch_a_id}/cancel")
    assert res_b_bcancel.status_code == 404
