# PurgeDoc QA access

- QA identity: `qa2.purgedoc@anclora.local`
- Frontend: `https://purgedoc.anclora.com`
- Backend: `https://api.purgedoc.anclora.com`
- Auth mechanism: closed-access email/password login with HttpOnly JWT cookies
- Secret source: encrypted AOS environment store; never commit or print it
- QA lifecycle: persistent dedicated user; `QA_DELETE_AFTER_TEST=false`

## Smoke procedure

Run `backend/.venv/bin/python scripts/qa/login-smoke.py` after the canonical QA
password has been materialized from the governed secret store. It verifies
login, authenticated `/api/auth/me`, and logout. Use synthetic PDF/DOCX fixtures
only.

`qa.purgedoc@anclora.local` is retired and must not be reactivated. Do not use
Toni's account, admin accounts, real documents, raw document contents, OCR text,
passwords, cookies, tokens, hashes, or database URLs in logs, reports, commits,
or screenshots.
