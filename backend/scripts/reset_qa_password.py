#!/usr/bin/env python3
"""Administrative CLI to reset the password of Anclora PurgeDoc's single
persistent QA account.

This is deliberately NOT a general-purpose password reset tool. It only ever
touches `users.password_hash` for exactly one hard-coded email:
`qa2.purgedoc@anclora.local`. Unlike a configurable allowlist, that email is
a constant in this module (QA_EMAIL) — it cannot be widened by an
environment variable, a CLI flag, or an allowlist entry. Even if a future
edit accidentally added another email to some allowlist elsewhere, this tool
would still refuse to act on it, because the comparison is against the
single hard-coded constant, not a list.

Design rationale for anyone reviewing this file (mirrors the equivalent
CleanSheet tool at anclora-cleansheet/backend/scripts/reset_qa_password.py):
- CLI, not an HTTP endpoint: an admin reset action has no legitimate reason
  to be reachable over the network surface at all.
- The new password is read interactively via `getpass` (hidden stdin) and is
  never accepted as a command-line argument, logged, or included in any
  exception message.
- This module intentionally does NOT call the shared `record_audit_event()`
  helper (backend/auth/security.py), because that helper performs its own
  internal commit and silently swallows exceptions on failure — which would
  make the atomicity of "update password_hash + write one audit row" harder
  to reason about and to test. Instead this module manages one explicit
  transaction itself, committing both changes together or rolling back both.
"""
from __future__ import annotations

import argparse
import getpass
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure the repo root (workspace dir containing the `backend` package) is
# importable regardless of the current working directory, matching the
# convention used by backend/scripts/manage_whitelist.py.
_backend_dir = Path(__file__).resolve().parents[1]
_workspace_dir = Path(__file__).resolve().parents[2]
for _p in (str(_workspace_dir), str(_backend_dir)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from backend.auth.database import SessionLocal  # noqa: E402
from backend.auth.models import UserRow, AuthAuditEventRow  # noqa: E402
from backend.auth.security import (  # noqa: E402
    hash_password,
    get_admin_emails,
    AUTH_PASSWORD_MIN_LENGTH,
)


class QAResetError(Exception):
    """Base class for all rejection reasons. Never includes secret material."""


class OperatorRequiredError(QAResetError):
    pass


class ConfirmationRequiredError(QAResetError):
    pass


class NotQAIdentityError(QAResetError):
    pass


class AdminAccountRejectedError(QAResetError):
    pass


class PasswordTooShortError(QAResetError):
    pass


class UserNotFoundError(QAResetError):
    pass


class AccountNotActiveError(QAResetError):
    pass


class PersistenceError(QAResetError):
    """Raised when the write transaction itself fails; the caller can assume
    the transaction was rolled back and nothing was persisted."""


# Hard-coded, non-configurable target identity. This is intentionally NOT an
# environment variable or a list: this tool resets exactly one account.
QA_EMAIL = "qa2.purgedoc@anclora.local"


def reset_qa_password(
    db,
    *,
    email: str,
    new_password: str,
    operator: str,
    confirmed: bool,
) -> str:
    """Core, directly-testable reset operation. Returns the affected user id.

    Every rejection path raises before any database write occurs. The single
    write (password_hash + one audit row) happens in one transaction; on any
    failure during that write, the transaction is rolled back and a
    PersistenceError is raised — nothing is left partially applied.
    """
    if not operator or not operator.strip():
        raise OperatorRequiredError("An operator identifier is required.")

    if not confirmed:
        raise ConfirmationRequiredError("Refusing to write without explicit confirmation.")

    clean_email = email.strip().lower()

    # Explicit, singular identity check — not a membership test against a
    # list. This is the core guarantee: no allowlist manipulation can widen
    # what this tool is willing to touch.
    if clean_email != QA_EMAIL:
        raise NotQAIdentityError(
            f"{clean_email} is not the authorized QA identity ({QA_EMAIL}). "
            "This command never resets any other account."
        )

    # Explicit admin rejection, independent of and in addition to the above.
    # Even though QA_EMAIL is a fixed constant unrelated to any admin list,
    # this check exists so that an admin account can never be reset through
    # this path even under a future refactor, and so the rejection reason is
    # unambiguous rather than incidental.
    admin_emails = get_admin_emails()
    if clean_email in admin_emails:
        raise AdminAccountRejectedError(
            f"{clean_email} is an administrative account; this command refuses to touch admin accounts."
        )

    if len(new_password) < AUTH_PASSWORD_MIN_LENGTH:
        raise PasswordTooShortError(
            f"Password must be at least {AUTH_PASSWORD_MIN_LENGTH} characters."
        )

    user = db.query(UserRow).filter(UserRow.email == clean_email).first()
    if user is None:
        raise UserNotFoundError(f"No user exists for {clean_email}.")

    if user.status != "active":
        raise AccountNotActiveError(
            f"Account status is '{user.status}', not 'active'. This command does not reactivate accounts."
        )

    new_hash = hash_password(new_password)

    try:
        user.password_hash = new_hash
        user.updated_at = datetime.now(timezone.utc)
        db.add(
            AuthAuditEventRow(
                event="qa_password_reset_cli",
                email=clean_email,
                user_id=user.id,
                metadata_json={"operator": operator},
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise PersistenceError("Failed to persist the password reset; transaction rolled back.") from exc

    return user.id


def _print_preflight_summary(email: str, operator: str) -> None:
    print("-----------------------------------------------------------------")
    print("QA PASSWORD RESET — PRE-WRITE SUMMARY")
    print("-----------------------------------------------------------------")
    print(f"QA email:    {email}")
    print(f"Operator:    {operator}")
    print("Action:      reset users.password_hash for this QA account only")
    print("The new password will NOT be displayed or logged at any point.")
    print("-----------------------------------------------------------------")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Reset the password of Anclora PurgeDoc's single persistent QA "
            f"account ({QA_EMAIL}). Never a generic reset tool."
        )
    )
    parser.add_argument("--operator", required=True, help="Identifier of the person performing this reset")
    parser.add_argument(
        "--confirm-qa-reset",
        action="store_true",
        help="Required. Without this flag the command refuses to write.",
    )
    args = parser.parse_args()

    if not args.operator.strip():
        print("ERROR: --operator is required and cannot be blank.", file=sys.stderr)
        sys.exit(1)
    if not args.confirm_qa_reset:
        print("ERROR: refusing to proceed without --confirm-qa-reset.", file=sys.stderr)
        sys.exit(1)
    if QA_EMAIL in get_admin_emails():
        print(f"ERROR: {QA_EMAIL} is an administrative account; refusing.", file=sys.stderr)
        sys.exit(1)

    _print_preflight_summary(QA_EMAIL, args.operator)

    typed_email = input(f"Type the QA email to confirm ({QA_EMAIL}): ").strip().lower()
    if typed_email != QA_EMAIL:
        print("ERROR: typed email did not match. Nothing was changed.", file=sys.stderr)
        sys.exit(1)

    new_password = getpass.getpass("New password (hidden, will not be echoed): ")
    confirm_password = getpass.getpass("Confirm new password: ")
    if new_password != confirm_password:
        print("ERROR: passwords did not match. Nothing was changed.", file=sys.stderr)
        sys.exit(1)

    db = SessionLocal()
    try:
        user_id = reset_qa_password(
            db,
            email=QA_EMAIL,
            new_password=new_password,
            operator=args.operator,
            confirmed=args.confirm_qa_reset,
        )
    except QAResetError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()

    print("-----------------------------------------------------------------")
    print(f"Password reset succeeded for {QA_EMAIL} (user id: {user_id}).")
    print("An audit event 'qa_password_reset_cli' was recorded (no secrets).")
    print("-----------------------------------------------------------------")


if __name__ == "__main__":
    main()
