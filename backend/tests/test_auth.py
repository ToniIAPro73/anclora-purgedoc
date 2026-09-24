import os
import uuid
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

os.environ["AUTH_ADMIN_EMAILS"] = "admin@anclora.local"
os.environ["AUTH_PASSWORD_MIN_LENGTH"] = "12"

from backend.server import app
from backend.auth.database import SessionLocal
from backend.auth.models import UserRow, AuthWhitelistRow, AuthAuditEventRow
from backend.auth.security import hash_password, hash_token, generate_raw_token, create_access_token

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def admin_user(db_session):
    admin = db_session.query(UserRow).filter(UserRow.email == "admin@anclora.local").first()
    if not admin:
        admin = UserRow(
            id=str(uuid.uuid4()),
            email="admin@anclora.local",
            password_hash=hash_password("AdminSecurePassword123!"),
            display_name="Admin",
            status="active"
        )
        db_session.add(admin)
        db_session.flush()

    wl = db_session.query(AuthWhitelistRow).filter(AuthWhitelistRow.email == "admin@anclora.local").first()
    if not wl:
        wl = AuthWhitelistRow(
            id=str(uuid.uuid4()),
            email="admin@anclora.local",
            status="active",
            user_id=admin.id,
            created_by="system",
            activated_at=datetime.now(timezone.utc)
        )
        db_session.add(wl)
    else:
        wl.user_id = admin.id
        wl.status = "active"
    db_session.commit()
    db_session.refresh(admin)
    return admin

def test_public_registration_disabled(client):
    r = client.post("/api/auth/register", json={"email": "hacker@evil.com", "password": "password12345"})
    assert r.status_code == 403
    assert "deshabilitado" in r.text.lower() or "invitación" in r.text.lower()

def test_whitelist_admin_authorization(client, admin_user):
    # Unauthenticated request to /api/auth/whitelist -> 401
    r = client.post("/api/auth/whitelist", json={"email": "newuser@corp.com"})
    assert r.status_code == 401

    # Login as admin
    login_res = client.post("/api/auth/login", json={"email": "admin@anclora.local", "password": "AdminSecurePassword123!"})
    assert login_res.status_code == 200

    # Admin adds email to whitelist
    invited_email = f"invited_{uuid.uuid4().hex[:6]}@anclora.com"
    r = client.post("/api/auth/whitelist", json={"email": invited_email})
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == invited_email
    assert data["status"] == "pending"
    assert "activation_token" in data
    raw_token = data["activation_token"]

    # Verify DB stores SHA-256 only, NOT raw token
    db = SessionLocal()
    try:
        entry = db.query(AuthWhitelistRow).filter(AuthWhitelistRow.email == invited_email).first()
        assert entry is not None
        assert entry.token_hash == hash_token(raw_token)
        assert raw_token not in entry.token_hash
        assert len(entry.token_hash) == 64
    finally:
        db.close()

def test_login_wrong_password_and_nonexistent_email_generic(client, admin_user):
    # Nonexistent email -> generic 401
    r1 = client.post("/api/auth/login", json={"email": "nonexistent@example.com", "password": "AnyPassword123!"})
    assert r1.status_code == 401
    assert r1.json()["detail"] == "Credenciales incorrectas."

    # Existing email wrong password -> exact same generic 401
    r2 = client.post("/api/auth/login", json={"email": "admin@anclora.local", "password": "WrongPassword123!"})
    assert r2.status_code == 401
    assert r2.json()["detail"] == "Credenciales incorrectas."

def test_token_expiry_validation(client, db_session):
    expired_email = f"expired_{uuid.uuid4().hex[:6]}@anclora.com"
    expired_raw = generate_raw_token()
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    entry = AuthWhitelistRow(
        id=str(uuid.uuid4()),
        email=expired_email,
        status="pending",
        token_hash=hash_token(expired_raw),
        expires_at=past,
        created_by="admin"
    )
    db_session.add(entry)
    db_session.commit()

    r = client.get(f"/api/auth/activation/validate?token={expired_raw}")
    assert r.status_code == 400
    assert "expirada" in r.text.lower() or "invitación" in r.text.lower()

def test_activation_flow_and_token_reuse(client, admin_user, db_session):
    # 1. Login as admin and invite user
    client.post("/api/auth/login", json={"email": "admin@anclora.local", "password": "AdminSecurePassword123!"})
    user_email = f"activate_{uuid.uuid4().hex[:6]}@anclora.com"
    inv_res = client.post("/api/auth/whitelist", json={"email": user_email})
    assert inv_res.status_code == 200
    raw_token = inv_res.json()["activation_token"]

    # 2. Validate token
    val_res = client.get(f"/api/auth/activation/validate?token={raw_token}")
    assert val_res.status_code == 200
    assert val_res.json()["valid"] is True
    assert val_res.json()["email"] == user_email

    # 3. Reject password under 12 characters
    short_pw_res = client.post("/api/auth/activate", json={
        "token": raw_token,
        "password": "short",
        "display_name": "Test User"
    })
    assert short_pw_res.status_code == 400
    assert "12" in short_pw_res.text

    # 4. Successful activation
    good_password = "ValidSecurePassword123!"
    act_res = client.post("/api/auth/activate", json={
        "token": raw_token,
        "password": good_password,
        "display_name": "Test User"
    })
    assert act_res.status_code == 200
    act_data = act_res.json()
    assert act_data["email"] == user_email

    # Verify cookies set
    assert "access_token" in client.cookies

    # 5. Check session /me
    me_res = client.get("/api/auth/me")
    assert me_res.status_code == 200
    assert me_res.json()["authenticated"] is True
    assert me_res.json()["user"]["email"] == user_email

    # 6. Reject token reuse
    reuse_res = client.post("/api/auth/activate", json={
        "token": raw_token,
        "password": good_password
    })
    assert reuse_res.status_code == 400

    # 7. Logout then normal login works
    logout_res = client.post("/api/auth/logout")
    assert logout_res.status_code == 200
    me_logged_out = client.get("/api/auth/me")
    assert me_logged_out.json()["authenticated"] is False

    login_res = client.post("/api/auth/login", json={"email": user_email, "password": good_password})
    assert login_res.status_code == 200
    assert client.get("/api/auth/me").json()["authenticated"] is True

def test_whitelist_listing_never_leaks_secrets(client, admin_user):
    client.post("/api/auth/login", json={"email": "admin@anclora.local", "password": "AdminSecurePassword123!"})
    res = client.get("/api/auth/whitelist")
    assert res.status_code == 200
    entries = res.json()
    assert len(entries) > 0
    for entry in entries:
        assert "token_hash" not in entry
        assert "activation_token" not in entry
        assert "password" not in entry
        assert "password_hash" not in entry

def test_immediate_revocation_invalidates_active_session(client, admin_user, db_session):
    # Create and activate user
    client.post("/api/auth/login", json={"email": "admin@anclora.local", "password": "AdminSecurePassword123!"})
    target_email = f"revoked_{uuid.uuid4().hex[:6]}@anclora.com"
    inv_res = client.post("/api/auth/whitelist", json={"email": target_email})
    raw_token = inv_res.json()["activation_token"]
    entry_id = inv_res.json()["id"]

    act_client = TestClient(app)
    act_client.post("/api/auth/activate", json={
        "token": raw_token,
        "password": "ValidPassword123!",
        "display_name": "Target"
    })
    assert act_client.get("/api/auth/me").json()["authenticated"] is True

    # Admin revokes whitelist entry
    rev_res = client.post(f"/api/auth/whitelist/{entry_id}/revoke")
    assert rev_res.status_code == 200

    # Active session must be immediately rejected on next request
    me_revoked = act_client.get("/api/auth/me")
    assert me_revoked.json()["authenticated"] is False

    # Login attempt must be rejected
    login_revoked = act_client.post("/api/auth/login", json={"email": target_email, "password": "ValidPassword123!"})
    assert login_revoked.status_code == 401
