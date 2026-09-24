# Anclora PurgeDoc — Closed Access & Whitelist Architecture

## 1. Overview

Anclora PurgeDoc implements a strictly closed access model. Public open registration is disabled, and anonymous usage of processing endpoints is prohibited. User onboarding is gated by an administrative whitelist invitation system with single-use cryptographically secure tokens.

## 2. Route Architecture

| Route | Visibility | Purpose |
|---|---|---|
| `/` | Public | Brand landing page communicating real physical redaction capabilities, local OCR (spa+eng), spaCy NER + regex rules, fail-closed verification, and SHA-256 integrity audits. |
| `/login` | Public | Dedicated email & password authentication surface with show/hide password toggle, visible but disabled social buttons (Google & GitHub), and link to activation. |
| `/activate` | Public (Token Required) | Account activation screen validating invitation token, showing read-only email, and accepting user display name and password (minimum 12 characters). |
| `/app` | Protected | Authenticated PurgeDoc workspace. Unauthenticated visitors are routed to `/login`. Ephemeral sessions and batches are created only upon mounting `/app`. |

## 3. Authentication & Security Specifications

- **Password Hashing**: Argon2id via `argon2-cffi` (`time_cost=2, memory_cost=19456, parallelism=1`).
- **Session Tokens**: JWT access tokens (1 hour TTL) and refresh tokens (7 days TTL) issued via HttpOnly cookies (`access_token`, `refresh_token`).
  - In production (`APP_ENV=production`): `Secure=True; SameSite=None; Path=/` to support cross-subdomain API communication (`purgedoc.anclora.com` -> `api.purgedoc.anclora.com`).
  - In local development: `Secure=False; SameSite=Lax; Path=/`.
- **Active State Validation**: Every authenticated request evaluates both `user.status == 'active'` and `whitelist.status == 'active'` against the database in real time. If an invitation is revoked, active sessions are immediately invalidated regardless of JWT expiration.
- **Audit Logging**: All security actions (`login_succeeded`, `login_failed`, `activation_succeeded`, `activation_rejected`, `whitelist_added`, `whitelist_revoked`, `whitelist_token_rotated`) are logged to `auth_audit_events`.
- **Zero Secret Leakage**: Raw tokens, passwords, and JWTs are never persisted in plain text or returned in listing endpoints. Tokens are stored strictly as SHA-256 hashes (`token_hash`).

## 4. Administrative Whitelist Management

### Environment Configuration
- `AUTH_ADMIN_EMAILS`: Comma-separated list of administrator emails authorized to invoke admin whitelist endpoints.
- `AUTH_WHITELIST_TOKEN_TTL_HOURS`: Invitation token time-to-live (default: 72 hours).
- `AUTH_PASSWORD_MIN_LENGTH`: Minimum password length enforced during activation (default: 12 characters).

### Admin Endpoints
- `POST /api/auth/whitelist`: Create an invitation for an email. Returns single-use raw activation token.
- `GET /api/auth/whitelist`: List whitelist entries. Never exposes token hashes or credentials.
- `POST /api/auth/whitelist/{id}/rotate-token`: Regenerate and re-issue a fresh activation token.
- `POST /api/auth/whitelist/{id}/revoke`: Immediately revoke an invitation and disable any linked user account.

### Operator CLI
An operational CLI is provided at `backend/scripts/manage_whitelist.py` that interfaces directly with backend models:
```bash
# Add new invitation
python backend/scripts/manage_whitelist.py add --email user@example.com

# List invitations
python backend/scripts/manage_whitelist.py list

# Rotate token
python backend/scripts/manage_whitelist.py rotate --target user@example.com

# Revoke access
python backend/scripts/manage_whitelist.py revoke --target user@example.com
```

## 5. Anonymous API Closure & IDOR Hardening

All product endpoints require authenticated user access (`get_current_user_required`):
- `/api/sessions` (creates an ephemeral session bound to the authenticated user ID)
- `/api/documents/*`, `/api/matches/*`, `/api/batches/*`
- `/api/fixtures/*`, `/api/rules/*`, `/api/profiles`

### Object-Level Authorization (IDOR Mitigation)
- Sessions are owned by the creating user (`session_owners` table and in-memory session registry).
- Documents, batches, matches, page images, and downloads verify session ownership.
- Cross-user access attempts result in `404 Not Found` (fail-closed IDOR protection).
