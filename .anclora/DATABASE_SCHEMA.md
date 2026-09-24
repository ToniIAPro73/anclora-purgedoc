# PurgeDoc Database Schema & Privacy Architecture

Provider: Neon PostgreSQL (production) / SQLite (tests / CI).

## Alembic Revisions
1. `0001_metadata_only_schema`: Ephemeral document processing metadata & audit logs.
2. `0002_closed_access_auth`: Closed whitelist access control, user accounts, and session ownership.

---

## 1. Document Lifecycle & Audit Metadata (Alembic 0001)

This schema is a metadata/audit/lifecycle mirror only. **Active document bytes, OCR full text, extracted raw text, previews, output files, filenames, local file paths, .aprules passphrases, and raw PII remain strictly in memory or ephemeral local storage and NEVER enter the database.**

| Table | Purpose | Allowed content |
|---|---|---|
| `sessions` | Session lifecycle | IDs, statuses, timestamps |
| `batches` | Batch lifecycle | IDs, profile/ruleset IDs, counts |
| `documents` | Document lifecycle | IDs, MIME/size, SHA-256, statuses |
| `audit_records` | Verification summary | IDs, counts, hashes, safe metadata |
| `audit_items` | Redaction audit | type, page, status, hash, bbox |
| `lifecycle_tombstones` | Deletion evidence | ID, reason, timestamps |
| `alembic_version` | Migration state | Revision identifier |

---

## 2. Closed Whitelist & Authentication (Alembic 0002)

Persisting account email for user authentication is explicitly authorized under this architecture.

| Table | Purpose | Allowed content |
|---|---|---|
| `users` | Authenticated user accounts | id (UUID), email (unique, normalized), password_hash (Argon2id), display_name, status (`active` \| `disabled`), timestamps |
| `auth_whitelist` | Invitation whitelist | id (UUID), email (unique, normalized), status (`pending` \| `active` \| `revoked`), token_hash (SHA-256), expires_at, activated_at, revoked_at, user_id, created_by, timestamps |
| `auth_audit_events` | Security & auth telemetry | id, event_type, email, user_id, ip_address, user_agent, details (JSON), created_at |
| `session_owners` | Cross-user IDOR isolation | session_id (FK to `sessions.id`), user_id (FK to `users.id`), created_at |

---

## Strict Privacy Invariants

- **Raw PDF/DOCX bytes**: NEVER DATABASE.
- **OCR full text**: NEVER DATABASE.
- **Match raw sensitive text**: NEVER DATABASE.
- **Document filename**: NEVER DATABASE.
- **Local temporary paths**: NEVER DATABASE.
- **Ruleset passphrase**: NEVER DATABASE.
- **JWT secrets / tokens**: NEVER DATABASE.
- **Raw invitation tokens**: NEVER DATABASE (stored strictly as SHA-256 hash).
