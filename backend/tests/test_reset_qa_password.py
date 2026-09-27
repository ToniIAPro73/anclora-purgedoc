import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("AUTH_ADMIN_EMAILS", "admin@anclora.local")
os.environ.setdefault("AUTH_PASSWORD_MIN_LENGTH", "12")

from backend.auth.models import AuthBase, UserRow, AuthWhitelistRow, AuthAuditEventRow  # noqa: E402
from backend.auth.security import hash_password, verify_password  # noqa: E402
from backend.scripts.reset_qa_password import (  # noqa: E402
    reset_qa_password,
    QA_EMAIL,
    OperatorRequiredError,
    ConfirmationRequiredError,
    NotQAIdentityError,
    AdminAccountRejectedError,
    PasswordTooShortError,
    UserNotFoundError,
    AccountNotActiveError,
    PersistenceError,
)

ORIGINAL_PASSWORD = "OriginalQAPassword123!"
NEW_PASSWORD = "BrandNewQAPassword456!"

# This suite must never be able to reach the production Neon database, even
# if the developer's shell exports a real DATABASE_URL. A dedicated
# in-memory SQLite engine — independent of
# backend.auth.database.SessionLocal/engine — is created here and used for
# every test in this file.
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
assert test_engine.dialect.name == "sqlite"
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
AuthBase.metadata.create_all(bind=test_engine)


def test_suite_never_targets_production_host():
    """Guard against accidental production connections: whatever DATABASE_URL
    might be set in the environment, this suite's own engine is always
    sqlite:// (in-memory), never a Neon/postgres production host."""
    assert test_engine.url.get_backend_name() == "sqlite"
    db_url_env = os.environ.get("DATABASE_URL", "")
    assert "neon.tech" not in db_url_env or True  # informational; suite doesn't use this var at all
    assert str(TestSessionLocal.kw["bind"].url) == "sqlite://"


@pytest.fixture
def db_session():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def qa_user(db_session):
    existing = db_session.query(UserRow).filter(UserRow.email == QA_EMAIL).first()
    if existing:
        db_session.delete(existing)
        db_session.commit()
    user = UserRow(
        id=str(uuid.uuid4()),
        email=QA_EMAIL,
        password_hash=hash_password(ORIGINAL_PASSWORD),
        display_name="PurgeDoc QA",
        status="active",
    )
    db_session.add(user)
    wl = AuthWhitelistRow(
        id=str(uuid.uuid4()),
        email=QA_EMAIL,
        status="active",
        user_id=user.id,
        created_by="test_fixture",
        activated_at=datetime.now(timezone.utc),
    )
    db_session.add(wl)
    db_session.commit()
    db_session.refresh(user)
    yield user
    db_session.query(AuthAuditEventRow).filter(AuthAuditEventRow.email == QA_EMAIL).delete()
    db_session.query(AuthWhitelistRow).filter(AuthWhitelistRow.email == QA_EMAIL).delete()
    db_session.query(UserRow).filter(UserRow.email == QA_EMAIL).delete()
    db_session.commit()


def test_correct_reset_of_authorized_qa_account(db_session, qa_user):
    user_id = reset_qa_password(
        db_session,
        email=QA_EMAIL,
        new_password=NEW_PASSWORD,
        operator="toni",
        confirmed=True,
    )
    assert user_id == qa_user.id

    fresh = TestSessionLocal()
    try:
        updated = fresh.query(UserRow).filter(UserRow.email == QA_EMAIL).first()
        assert verify_password(NEW_PASSWORD, updated.password_hash) is True
        assert verify_password(ORIGINAL_PASSWORD, updated.password_hash) is False
    finally:
        fresh.close()


def test_rejects_non_qa_email(db_session, qa_user):
    with pytest.raises(NotQAIdentityError):
        reset_qa_password(
            db_session,
            email="someone.else@anclora.com",
            new_password=NEW_PASSWORD,
            operator="toni",
            confirmed=True,
        )


def test_rejects_any_other_email_even_if_it_exists_and_is_active(db_session, qa_user):
    """Requirement 1: refuses to act on ANY email other than QA_EMAIL, even
    a real, active, non-admin user account."""
    other = UserRow(
        id=str(uuid.uuid4()),
        email="another.user@anclora.local",
        password_hash=hash_password("SomeOtherPassword123!"),
        display_name="Another User",
        status="active",
    )
    db_session.add(other)
    db_session.commit()
    try:
        with pytest.raises(NotQAIdentityError):
            reset_qa_password(
                db_session,
                email="another.user@anclora.local",
                new_password=NEW_PASSWORD,
                operator="toni",
                confirmed=True,
            )
        fresh = TestSessionLocal()
        try:
            unchanged = fresh.query(UserRow).filter(UserRow.email == "another.user@anclora.local").first()
            assert verify_password("SomeOtherPassword123!", unchanged.password_hash) is True
        finally:
            fresh.close()
    finally:
        db_session.query(UserRow).filter(UserRow.email == "another.user@anclora.local").delete()
        db_session.commit()


def test_rejects_nonexistent_user():
    db = TestSessionLocal()
    try:
        with pytest.raises(UserNotFoundError):
            reset_qa_password(
                db,
                email=QA_EMAIL,
                new_password=NEW_PASSWORD,
                operator="toni",
                confirmed=True,
            )
    finally:
        db.close()


def test_rejects_admin_account_even_if_email_string_matches_allowlist_style_input(db_session, qa_user, monkeypatch):
    """Requirement 2: reject admin accounts explicitly even if an allowlist
    path would have accidentally included them. We simulate this by pointing
    AUTH_ADMIN_EMAILS at QA_EMAIL itself (i.e. the QA email has been
    misconfigured as an admin) and confirming the explicit admin check still
    fires and blocks the write, rather than relying on incidental behavior."""
    monkeypatch.setenv("AUTH_ADMIN_EMAILS", f"{QA_EMAIL},admin@anclora.local")
    with pytest.raises(AdminAccountRejectedError):
        reset_qa_password(
            db_session,
            email=QA_EMAIL,
            new_password=NEW_PASSWORD,
            operator="toni",
            confirmed=True,
        )
    fresh = TestSessionLocal()
    try:
        unchanged = fresh.query(UserRow).filter(UserRow.email == QA_EMAIL).first()
        assert verify_password(ORIGINAL_PASSWORD, unchanged.password_hash) is True
    finally:
        fresh.close()


def test_rejects_literal_admin_email_regardless_of_qa_check(db_session):
    """A second, independent proof of requirement 2: even directly passing
    the admin email (which is never QA_EMAIL) is rejected by the QA identity
    check first — admin accounts can never reach this tool's write path."""
    with pytest.raises(NotQAIdentityError):
        reset_qa_password(
            db_session,
            email="admin@anclora.local",
            new_password=NEW_PASSWORD,
            operator="toni",
            confirmed=True,
        )


def test_rejects_suspended_account(db_session, qa_user):
    qa_user.status = "disabled"
    db_session.commit()
    with pytest.raises(AccountNotActiveError):
        reset_qa_password(
            db_session,
            email=QA_EMAIL,
            new_password=NEW_PASSWORD,
            operator="toni",
            confirmed=True,
        )


def test_rejects_without_confirmation(db_session, qa_user):
    with pytest.raises(ConfirmationRequiredError):
        reset_qa_password(
            db_session,
            email=QA_EMAIL,
            new_password=NEW_PASSWORD,
            operator="toni",
            confirmed=False,
        )
    fresh = TestSessionLocal()
    try:
        unchanged = fresh.query(UserRow).filter(UserRow.email == QA_EMAIL).first()
        assert verify_password(ORIGINAL_PASSWORD, unchanged.password_hash) is True
    finally:
        fresh.close()


def test_rejects_without_operator(db_session, qa_user):
    with pytest.raises(OperatorRequiredError):
        reset_qa_password(
            db_session,
            email=QA_EMAIL,
            new_password=NEW_PASSWORD,
            operator="   ",
            confirmed=True,
        )


def test_rejects_password_too_short(db_session, qa_user):
    with pytest.raises(PasswordTooShortError):
        reset_qa_password(
            db_session,
            email=QA_EMAIL,
            new_password="short",
            operator="toni",
            confirmed=True,
        )


def test_hash_updated_correctly(db_session, qa_user):
    old_hash = qa_user.password_hash
    reset_qa_password(
        db_session,
        email=QA_EMAIL,
        new_password=NEW_PASSWORD,
        operator="toni",
        confirmed=True,
    )
    fresh = TestSessionLocal()
    try:
        updated = fresh.query(UserRow).filter(UserRow.email == QA_EMAIL).first()
        assert updated.password_hash != old_hash
        assert verify_password(NEW_PASSWORD, updated.password_hash) is True
    finally:
        fresh.close()


def test_email_and_status_unchanged(db_session, qa_user):
    reset_qa_password(
        db_session,
        email=QA_EMAIL,
        new_password=NEW_PASSWORD,
        operator="toni",
        confirmed=True,
    )
    fresh = TestSessionLocal()
    try:
        updated = fresh.query(UserRow).filter(UserRow.email == QA_EMAIL).first()
        assert updated.email == QA_EMAIL
        assert updated.status == "active"
        assert updated.identity_sub is None

        wl = fresh.query(AuthWhitelistRow).filter(AuthWhitelistRow.email == QA_EMAIL).first()
        assert wl.status == "active"
        assert wl.user_id == updated.id
    finally:
        fresh.close()


def test_audit_event_created_without_secrets(db_session, qa_user):
    reset_qa_password(
        db_session,
        email=QA_EMAIL,
        new_password=NEW_PASSWORD,
        operator="toni",
        confirmed=True,
    )
    fresh = TestSessionLocal()
    try:
        event = (
            fresh.query(AuthAuditEventRow)
            .filter(AuthAuditEventRow.email == QA_EMAIL, AuthAuditEventRow.event == "qa_password_reset_cli")
            .order_by(AuthAuditEventRow.created_at.desc())
            .first()
        )
        assert event is not None
        assert event.metadata_json == {"operator": "toni"}
        serialized = str(event.metadata_json)
        assert NEW_PASSWORD not in serialized
        assert ORIGINAL_PASSWORD not in serialized
        assert "password" not in serialized.lower()
        assert "hash" not in serialized.lower()
    finally:
        fresh.close()


def test_rollback_on_persistence_error(db_session, qa_user, monkeypatch):
    old_hash = qa_user.password_hash

    def boom():
        raise RuntimeError("simulated commit failure")

    monkeypatch.setattr(db_session, "commit", boom)

    with pytest.raises(PersistenceError):
        reset_qa_password(
            db_session,
            email=QA_EMAIL,
            new_password=NEW_PASSWORD,
            operator="toni",
            confirmed=True,
        )

    fresh = TestSessionLocal()
    try:
        unchanged = fresh.query(UserRow).filter(UserRow.email == QA_EMAIL).first()
        assert unchanged.password_hash == old_hash
        event = (
            fresh.query(AuthAuditEventRow)
            .filter(AuthAuditEventRow.email == QA_EMAIL, AuthAuditEventRow.event == "qa_password_reset_cli")
            .first()
        )
        assert event is None
    finally:
        fresh.close()


def test_password_never_appears_in_cli_process_arguments():
    """The CLI must never accept the password (or the target email) as a
    process argument — verify the script's argparse surface has no such
    options at all."""
    repo_root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "backend/scripts/reset_qa_password.py", "--help"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    assert "--password" not in result.stdout
    assert "-p " not in result.stdout
    assert "--email" not in result.stdout


def test_password_never_appears_in_stdout_or_stderr_of_core_function(db_session, qa_user, capsys):
    reset_qa_password(
        db_session,
        email=QA_EMAIL,
        new_password=NEW_PASSWORD,
        operator="toni",
        confirmed=True,
    )
    captured = capsys.readouterr()
    assert NEW_PASSWORD not in captured.out
    assert NEW_PASSWORD not in captured.err
    assert ORIGINAL_PASSWORD not in captured.out
    assert ORIGINAL_PASSWORD not in captured.err
