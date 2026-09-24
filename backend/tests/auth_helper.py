import uuid
import requests
from datetime import datetime, timezone
from backend.auth.database import SessionLocal
from backend.auth.models import UserRow, AuthWhitelistRow
from backend.auth.security import hash_password

TEST_USER_EMAIL = "qa.purgedoc@anclora.local"
TEST_USER_PASSWORD = "QAPurgeDocPassword123!"


def ensure_test_user_in_db():
    db = SessionLocal()
    try:
        user = None
        try:
            user = db.query(UserRow).filter(UserRow.email == TEST_USER_EMAIL).first()
            if not user:
                user = UserRow(
                    id=str(uuid.uuid4()),
                    email=TEST_USER_EMAIL,
                    password_hash=hash_password(TEST_USER_PASSWORD),
                    display_name="QA PurgeDoc",
                    status="active"
                )
                db.add(user)
                db.commit()
            else:
                user.status = "active"
                user.password_hash = hash_password(TEST_USER_PASSWORD)
                db.commit()
        except Exception:
            db.rollback()
            user = db.query(UserRow).filter(UserRow.email == TEST_USER_EMAIL).first()

        try:
            wl = db.query(AuthWhitelistRow).filter(AuthWhitelistRow.email == TEST_USER_EMAIL).first()
            if not wl:
                wl = AuthWhitelistRow(
                    id=str(uuid.uuid4()),
                    email=TEST_USER_EMAIL,
                    status="active",
                    user_id=user.id if user else None,
                    created_by="system",
                    activated_at=datetime.now(timezone.utc)
                )
                db.add(wl)
                db.commit()
            else:
                if user:
                    wl.user_id = user.id
                wl.status = "active"
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


def get_authenticated_session(base_url: str) -> requests.Session:
    ensure_test_user_in_db()
    s = requests.Session()
    adapter = requests.adapters.HTTPAdapter(max_retries=3)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    r = s.post(
        f"{base_url}/api/auth/login",
        json={"email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD},
        timeout=10
    )
    if r.status_code != 200:
        raise RuntimeError(f"Failed to authenticate test session: {r.status_code} {r.text}")
    return s
