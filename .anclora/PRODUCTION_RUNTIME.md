# Anclora Purgedoc — Production Runtime Contract

PRODUCTION_RUNTIME_MANIFEST_VERSION=2.0
STATUS=BOOTSTRAP_DECLARED

## Deployment infrastructure

VERCEL_PROJECT_NAME=anclora-purgedoc
VERCEL_PROJECT_ID=prj_R4vPPL8ufnaqdGKBekjgmNiP5DrF
VERCEL_ROOT_DIRECTORY=frontend
VERCEL_FRAMEWORK=create-react-app
VERCEL_PRODUCTION_BRANCH=main
GITHUB_DEFAULT_BRANCH=development
PRODUCTION_DOMAIN=purgedoc.anclora.com
DNS_PROVIDER=Hostinger
DNS_STATUS=CONFIGURED_TLS_PENDING
BACKEND_RUNTIME_EXTERNAL_REQUIRED=true
NEON_RESOURCE_NAME=anclora-purgedoc-db
NEON_RESOURCE_ID=store_YVnSjBw8FknekSJt
DATABASE_RESOURCE=PROVISIONED_AND_MIGRATED_METADATA_ONLY
DATABASE_RUNTIME_SCOPE=metadata_only

The Vercel project is frontend-only (`frontend/`). The FastAPI backend remains an
external runtime because OCR, native document tooling, SSE, in-process sessions
and ephemeral storage are not being adapted to Vercel Serverless. The Neon
resource is connected to Vercel Production, Preview and Development and local
environment values are configured, but the current PurgeDoc runtime does not
consume PostgreSQL. No document, PII or session persistence is introduced.
DNS remains authoritative at Hostinger.

Every statement below was derived from the code at governance bootstrap time. Anything not
defined in the repository is marked `NOT_DECLARED`; do not invent it.

## Runtime topology

```text
React 19 SPA (CRA 5 + CRACO, Yarn 1)
   └─ axios → ${REACT_APP_BACKEND_URL}/api
FastAPI backend (backend/server.py, uvicorn, port 8001 by convention)
   ├─ Detection: spaCy es_core_news_sm + en_core_web_sm, YAML regex profiles, RE2 custom rules
   ├─ PDF: PyMuPDF (apply_redactions + garbage collection), pypdf/pdfminer for verification
   ├─ DOCX: python-docx + lxml OOXML sanitization; optional LibreOffice preview conversion
   ├─ OCR: Tesseract (pytesseract, lang "spa+eng") with OpenCV deskew
   ├─ Fail-closed verification after purge
   ├─ Audit: JSON / PDF (reportlab) / CSV with SHA-256 hashes, no clear-text PII
   ├─ .aprules export/import: AES-256-GCM + Argon2id (cryptography), AAD-bound envelope
   └─ Ephemeral storage: local filesystem under TEMP_ROOT + in-process memory
```

LOCAL_RUNTIME_MODEL=PRODUCTION_BACKED_METADATA_ONLY
DATABASE_PROVIDER=Neon PostgreSQL
DATABASE_CONTENT_SCOPE=SANITIZED_METADATA_ONLY
PERSISTENT_STORAGE=SANITIZED_METADATA_ONLY
EXTERNAL_AI_OR_CLOUD_CALLS=NONE
PRODUCTION_DEPLOYMENT_TARGET=NOT_DECLARED
BACKEND_RUNTIME_PROVIDER=Contabo VPS
BACKEND_RUNTIME_CONTAINERIZED=true
BACKEND_REVERSE_PROXY=Caddy
BACKEND_DEPLOY_SOURCE=main
BACKEND_DEPLOY_MODEL=Docker image pinned by SHA
BACKEND_PRODUCTION_URL=https://api.purgedoc.anclora.com
BACKEND_RUNTIME_MODE=SINGLE_INSTANCE_EPHEMERAL_PROCESSING
DOCUMENT_STORAGE=EPHEMERAL
PRODUCTION_URL=NOT_DECLARED
RUNTIME_VENDOR_DEPENDENCY=NONE
CODING_AGENT_VENDOR_DEPENDENCY=NONE
EMERGENT_RUNTIME_DEPENDENCY=NONE
EXTERNAL_TELEMETRY=NONE

Raw active sessions, batches, custom rulesets, upload bytes and the SSE event bus live in
process memory (`backend/server.py`, `backend/services/sessions.py`,
`backend/services/event_bus.py`). Only sanitized metadata is mirrored to PostgreSQL;
raw state is lost on restart and is not shared across processes, so the backend remains
effectively single-instance. Governed migrations historically applied only to the
metadata schema; see the scoped exception below for the closed-access auth schema.

PRODUCTION_MIGRATIONS_ALLOWED=true
MIGRATION_SYSTEM=Alembic
MIGRATION_CONFIRMATION_REQUIRED=true

### Scoped migration authorization (active)

`PRODUCTION_MIGRATIONS_ALLOWED` was flipped from `false` to `true` as a
**scoped exception**, not a blanket standing permission. It authorizes
exactly one thing:

```text
MIGRATION_AUTHORIZATION_SCOPE=identity_sub_only
MIGRATION_AUTHORIZED_REVISIONS=0003_add_identity_sub
MIGRATION_AUTHORIZATION_REASON=Additive, nullable, unique users.identity_sub column required by the Anclora Identity OIDC pilot (Wave 1); see docs/identity/ANCLORA_IDENTITY_WAVE1_CONTRACT.md in anclora-identity and docs/governance/proposal-enable-identity-sub-migration.md in this repository.
MIGRATION_AUTHORIZATION_OWNER=Toni
MIGRATION_AUTHORIZATION_DATE=2026-09-27
MIGRATION_AUTHORIZATION_ROLLBACK_PROCEDURE=docs/deployment/migration-identity-sub-runbook.md, section 16 (alembic downgrade 0002_closed_access_auth)
MIGRATION_AUTHORIZATION_REVIEW_CONDITION=Revisit this authorization once revision 0003_add_identity_sub has been applied to production and verified per the runbook; do not treat it as covering any later revision without a new, separately dated authorization entry below.
```

This authorization explicitly does **not**:

- authorize destructive migrations (column drops, table drops, resets) of
  any kind;
- authorize a database reset of any kind;
- authorize any Alembic revision other than `0003_add_identity_sub`;
- activate `ANCLORA_IDENTITY_ENABLED` — that remains a fully separate flag,
  set independently, and must stay `false` until after this migration is
  applied and the existing login path is re-verified (see the runbook);
- authorize any automatic deployment — `AUTO_PROMOTE=false` (below) is
  unaffected by this entry;
- extend `MIGRATION_CONFIRMATION_REQUIRED` away from `true` — every
  execution against production, including this one, still requires Toni's
  explicit per-run confirmation separate from this contract flag being
  `true`. This repository previously declared no such field at all; it is
  added here specifically because a blanket `PRODUCTION_MIGRATIONS_ALLOWED=true`
  without a per-run gate would be insufficient control for an authentication
  schema change.

#### Migration authorization log

| Date | Revision(s) authorized | Scope | Owner | Status |
| --- | --- | --- | --- | --- |
| 2026-09-27 | `0003_add_identity_sub` | Additive `users.identity_sub` column + unique index only | Toni | Authorized, not yet executed |

Any future migration requires its own dated row in this table before
`PRODUCTION_MIGRATIONS_ALLOWED=true` may be relied upon for it — this table,
not the bare flag value, is the source of truth for what is actually
authorized at any given time.

## Toolchain

| Component | Version / source |
| --- | --- |
| Python | 3.12 (pins such as numpy 2.4 / pandas 3.0 require >= 3.11) |
| Node | 22 in CI (react-scripts 5); local Node 20+ works |
| Package manager | Yarn 1.22.22 (`packageManager` field, `frontend/yarn.lock`) |
| spaCy models | wheels pinned in `backend/requirements.txt` |

Native/system dependencies:

- `tesseract-ocr` with `eng` and `spa` language data — required (OCR and security tests).
- LibreOffice `soffice` — optional; DOCX preview falls back to a PyMuPDF-generated PDF.
- OpenCV uses `opencv-python-headless` (no system GUI libs needed).

## Local runtime

```bash
# backend (from repo root)
python3.12 -m venv backend/venv && source backend/venv/bin/activate
pip install -r backend/requirements.txt   # public PyPI/GitHub sources only
PYTHONPATH=. uvicorn backend.server:app --host 127.0.0.1 --port 8001

# frontend
cd frontend && yarn install --frozen-lockfile && yarn start
```

The backend does not load `.env` files itself; variables must be exported in the process
environment. On boot `generate_all_fixtures()` (re)writes synthetic fixtures in
`backend/fixtures/` (gitignored).

All Python dependencies resolve from public PyPI, plus the spaCy model wheels pinned to
`github.com/explosion/spacy-models` releases. Frontend dependencies resolve from the public npm
registry through `frontend/yarn.lock`. No private package index is required.

The only remote resource the UI loads is the Inter webfont from Google Fonts
(`frontend/public/index.html`); the app still works without it. There is no analytics or
telemetry, and no document data leaves the backend.

## Environment contract

Backend (read by code, defaults in parentheses):

| Variable | Used in | Purpose |
| --- | --- | --- |
| `CORS_ORIGINS` (`*`) | `server.py` | Comma-separated allowed origins |
| `MAX_UPLOAD_MB` (25) | `server.py` | Single upload size limit |
| `TEMP_ROOT` (`/tmp/anclora-purgedoc`) | `sessions.py`, `lifecycle.py` | Ephemeral artifact root |
| `BATCH_MAX_DOCUMENTS` (10) | `batch.py` | Documents per batch |
| `BATCH_MAX_FILE_SIZE_MB` (25) | `batch.py` | Per-file batch limit |
| `BATCH_MAX_TOTAL_SIZE_MB` (100) | `batch.py` | Total batch size |
| `BATCH_MAX_CONCURRENT_DOCUMENTS` (2) | `batch.py` | Concurrency semaphore |
| `SESSION_TTL_MINUTES` (60) | `sessions.py`, `lifecycle.py` | Session inactivity TTL |
| `SOURCE_DOCUMENT_TTL_MINUTES` (15) | `lifecycle.py` | Source document TTL |
| `INTERMEDIATE_ARTIFACT_TTL_MINUTES` (15) | `lifecycle.py` | OCR/deskew/preview TTL |
| `VERIFIED_OUTPUT_TTL_MINUTES` (60) | `lifecycle.py` | Purged output TTL |
| `AUDIT_ARTIFACT_TTL_MINUTES` (60) | `lifecycle.py` | Audit artifact TTL |
| `BATCH_ARTIFACT_TTL_MINUTES` (60) | `lifecycle.py` | Batch ZIP TTL |
| `SSE_HISTORY_TTL_MINUTES` (30) | `lifecycle.py` | SSE history TTL |
| `CLEANUP_INTERVAL_SECONDS` (60) | `lifecycle.py` | Cleanup tick interval |

Frontend: `REACT_APP_BACKEND_URL` (required) and `ENABLE_HEALTH_CHECK` (dev server only,
`craco.config.js`).

Tests: `REACT_APP_BACKEND_URL` selects the backend for HTTP tests; `TESSDATA_PREFIX` may point
Tesseract to language data.

Names and safe placeholders live in `backend/.env.example` and `frontend/.env.example`. Local
values go in gitignored `.env.local` files with mode `0600`. No secret is currently required.

## Document lifecycle and privacy

- Uploads accept only `.pdf` and `.docx`. Files are written to
  `TEMP_ROOT/{session_id}/...` and raw bytes are cached in process memory.
- TTLs are listed above. Manual deletion is exposed by `DELETE /api/sessions/{id}` and
  `DELETE /api/batches/{id}`. `LifecycleManager.run_periodic_cleanup_tick` exists, but no
  background scheduler invoking it is wired in `backend/server.py` (observed; not changed).
- Deletion covers files under `TEMP_ROOT` only; it is not secure hardware erasure.
- Purge is irreversible and requires human confirmation; verification is fail-closed.
- Audits store SHA-256 hashes, never sensitive text.

## CORS

`CORSMiddleware` with `allow_origins=CORS_ORIGINS` (default `*`), `allow_credentials=True`,
all methods and headers. Production origins: `NOT_DECLARED`; set `CORS_ORIGINS` explicitly
for any exposed deployment.

## Secrets policy

No runtime secret is currently consumed. `.aprules` passphrases are user-supplied per request;
never commit `.env*` (except `*.env.example`), never print variable values,
never commit uploaded or processed documents.

## QA policy

QA_POLICY=WORKSPACE_PROPORTIONAL
QA_MODE_DEFAULT=AUTO
FAST_TARGETED_TESTING_POLICY=MINIMUM_SUFFICIENT_SET
FAST_FULL_TEST_SUITE_ALLOWED=false
STOP_WHEN_SUFFICIENT_EVIDENCE=true
TEST_EXECUTION_POLICY=BATCHED
FULL_GATES_AFTER_EVERY_EDIT=false
REPEAT_UNCHANGED_SUCCESSFUL_GATES=false
VISUAL_QA_EXECUTION=BY_QA_MODE

TOKEN_ECONOMY_POLICY=ADAPTIVE
CAVEMAN_MODE_DEFAULT=AUTO
CAVEMAN_GRANULARITY=TASK
QA_MINIMUM_FOR_DATABASE_MIGRATION=FULL
QA_MINIMUM_FOR_RELEASE_PROMOTION=FULL


QA_AUTH_MODEL=DEDICATED_USER
QA_PERSISTENT_IDENTITY=qa2.purgedoc@anclora.local
QA_REUSE=true
QA_DELETE_AFTER_TEST=false
QA_CREATE_IF_MISSING=true
QA_CREATION_CONFIRMATION_REQUIRED=true
QA_DATA=SYNTHETIC_FIXTURES_ONLY (`backend/fixtures_generator.py`)
VISUAL_QA_EXECUTION=BY_QA_MODE
REAL_DOCUMENTS_IN_TESTS=false

### QA identity history

`qa2.purgedoc@anclora.local` is the current, persistent, reusable QA identity
(created 2026-09-27 via the documented whitelist CLI —
`python backend/scripts/manage_whitelist.py add --email qa2.purgedoc@anclora.local`
— per Toni's explicit authorization). It carries no admin privileges (not
listed in `AUTH_ADMIN_EMAILS`) and must not be revoked or deleted after use;
`QA_DELETE_AFTER_TEST=false` applies to this identity going forward, unlike
what happened to its predecessor below.

`qa.purgedoc@anclora.local` (created 2026-09-24) is **retired**: `disabled`
at the `users` level and `revoked` at the `auth_whitelist` level, both
untouched by this change. **Do not reactivate it via direct SQL** — this
codebase has no supported application-level path to re-enable a disabled
user (`POST /api/auth/activate` rejects any email with an existing `users`
row regardless of status), so reinstating it would require bypassing
application logic entirely. `qa2.purgedoc@anclora.local` replaces it as the
identity to use going forward.

CORRECTION (2026-09-27): this section previously read "no user accounts or
authentication exist." That was accurate on 2026-09-23 when this file was
bootstrapped but became stale the next day: `backend/auth/*` (closed
whitelist access, real `users`/`auth_whitelist`/`auth_audit_events` tables,
Argon2id + JWT sessions) shipped in commit 56e541a (2026-09-24) and was never
reflected back into this contract. See `docs/auth-access.md` for the actual,
current auth model. `PRODUCTION_MIGRATIONS_ALLOWED` above governs the
closed-access auth schema too, not only the document-metadata mirror; as of
2026-09-27 it is `true` under the scoped, single-revision authorization
documented above (`identity_sub` only) — not a general reopening of
migrations for this schema.

## Test requirements

- Run from repo root with `PYTHONPATH=.`; `backend/pytest.ini` forces `-n 2 --dist loadscope`
  (pytest-xdist).
- Generate fixtures first (`python -c "from backend.fixtures_generator import generate_all_fixtures; generate_all_fixtures()"`);
  `backend/tests/security/test_temp_cleanup.py` reads them without generating.
- Deterministic in-process suite: all of `backend/tests/` except the three HTTP tests.
- HTTP tests (`test_api_e2e.py`, `test_encrypted_ruleset_http.py`,
  `security/test_sensitive_log_leakage.py`) need a running backend and
  `REACT_APP_BACKEND_URL` (default `http://127.0.0.1:8001`). They never fall back to a remote host.
- Frontend has no unit tests; `yarn test --watchAll=false --passWithNoTests` + `yarn build`.

## Git delivery

GIT_WORKFLOW_MODEL=FULL_PROMOTION
WORKING_BRANCH=development
DEFAULT_BRANCH=development
FEATURE_BRANCHES=DISALLOWED
PROMOTION_FLOW=development->staging->production->main
AUTO_PROMOTE=false
EXPLICIT_PROMOTION_ALLOWED=true
PROMOTION_AUTHORIZATION_SCOPE=CURRENT_TASK_OR_CONVERSATION
PROMOTION_REQUIRES_PRE_STEP_GATES=true
PROMOTION_STOP_ON_GATE_FAILURE=true
PROMOTION_FORCE_PUSH_ALLOWED=false
PROMOTION_OLD_AUTHORIZATION_PERSISTS=false

Work is committed and pushed to `development` by default. `staging`, `production` and `main`
move exclusively through `.github/workflows/promote.yml` on Toni's explicit current-task
instruction, subject to all release gates.
