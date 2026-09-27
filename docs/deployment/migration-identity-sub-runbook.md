# Runbook — Apply and Verify the `identity_sub` Migration (PurgeDoc)

Official, step-by-step procedure for revision `0003_add_identity_sub`
(`backend/alembic/versions/0003_add_identity_sub.py`). This document is the
missing runbook identified in the prior technical review — before it existed,
the migration command was only inferable from `alembic.ini`/`env.py`, not
documented as an official procedure.

**Status of this document**: procedure only. No migration has been run, and
no secret has been configured as part of writing this runbook.
`.anclora/PRODUCTION_RUNTIME.md` has been updated as part of this change —
see "Blocking authorization" immediately below for exactly what changed and
its scope.

## Blocking authorization (read this before anything else)

**Updated 2026-09-27**: `.anclora/PRODUCTION_RUNTIME.md` now reads
`PRODUCTION_MIGRATIONS_ALLOWED=true`, but this is a **scoped exception**, not
a blanket reopening — see that file's "Scoped migration authorization
(active)" section. It authorizes exactly one Alembic revision
(`0003_add_identity_sub`) and explicitly does not cover destructive changes,
resets, other revisions, OIDC activation, or automatic deployment.

This migration still **cannot** be run without one more thing:

1. `.anclora/PRODUCTION_RUNTIME.md` now also declares
   `MIGRATION_CONFIRMATION_REQUIRED=true` (newly added alongside the scoped
   authorization above — this repository previously had no such field).
   This is a **per-execution** gate, separate from the contract flag being
   `true` and separate from `ALLOW_PRODUCTION_MIGRATIONS=true` — satisfying
   the contract does not by itself satisfy this; Toni must explicitly confirm
   this specific run before step 8 below.
2. `backend/alembic/env.py`'s own `guard()` independently refuses to run
   against `DATABASE_TARGET=production` unless
   `ALLOW_PRODUCTION_MIGRATIONS=true` is explicitly set at execution time.
   This is a third, code-level gate, distinct from both of the above.

All three gates — contract scope, per-run confirmation, and the code-level
env guard — must be satisfied independently. None of them substitutes for
either of the others.

## Recommended order (do not reorder)

1. Authorize the contract (flip `PRODUCTION_MIGRATIONS_ALLOWED` — a
   documented, deliberate action, not part of this runbook).
2. Apply this migration.
3. Verify existing local (password/whitelist) login still works.
4. Deploy the `development` code that already references `identity_sub` in
   the ORM model (commit `831154c` and anything built on top of it).
5. Configure real OIDC secrets (`PURGEDOC_CLIENT_SECRET` in Identity,
   `ANCLORA_IDENTITY_CLIENT_SECRET`/`ANCLORA_IDENTITY_ISSUER_URL`/
   `ANCLORA_IDENTITY_SESSION_SECRET` in PurgeDoc).
6. Only after all of the above, enable `ANCLORA_IDENTITY_ENABLED=true`.

Step 4 must not happen before step 2: the ORM model already selects
`identity_sub` on every `db.query(UserRow)` call. Deploying that code against
a database that hasn't run this migration breaks **all** login, including
the existing password/whitelist path — not just OIDC.

---

## 1. Preconditions

- [ ] Contract authorization (step above) has been explicitly granted by Toni
      for this specific run — not inferred from a general "proceed" instruction.
- [ ] No other schema migration is in flight against the same database.
- [ ] The person running this has direct access to the production Neon
      connection string and to the VPS/container running the PurgeDoc backend
      (`api.purgedoc.anclora.com`).
- [ ] `ANCLORA_IDENTITY_ENABLED` is confirmed `false` in the current
      production environment (see step 5 below — checked here and re-checked
      after migration).

## 2. Unambiguous identification of the production database

Per PurgeDoc's own `.anclora/PRODUCTION_RUNTIME.md`:

```text
DATABASE_PROVIDER=Neon PostgreSQL
NEON_RESOURCE_NAME=anclora-purgedoc-db
NEON_RESOURCE_ID=store_YVnSjBw8FknekSJt
DATABASE_RUNTIME_SCOPE=metadata_only
```

Before running anything, confirm in the Neon console (or `neonctl`) that the
target connection string's resource id matches `store_YVnSjBw8FknekSJt`
exactly. The runtime connection string itself is **not** in this repository —
per `.anclora/PRODUCTION_RUNTIME.md`, it lives outside the repo at
`/home/toni/.config/anclora/runtime/purgedoc.env` (VPS-side) or in whatever
secret store holds the Neon connection string used by the backend process.
Do not source a connection string from memory or from an old local `.env` —
re-confirm it against the Neon console resource id above immediately before
use.

## 3. Required variables

| Variable | Value for this run | Source |
| --- | --- | --- |
| `DATABASE_URL` or `DATABASE_URL_UNPOOLED` | production Neon connection string | Neon console / VPS runtime env, confirmed against resource id above |
| `DATABASE_TARGET` | `production` | set explicitly for this command only |
| `ALLOW_PRODUCTION_MIGRATIONS` | `true` | set explicitly for this command only, per `env.py`'s `guard()` |

Do not export `ALLOW_PRODUCTION_MIGRATIONS=true` in a persistent shell profile
or `.env` file — set it inline, for this command, so it cannot be
accidentally reused for an unrelated future command.

## 4. Verify the branch and commit to be deployed

```bash
cd /Users/toni/Developer/anclora/anclora-purgedoc
git status --short          # must be empty
git branch --show-current   # must be: development
git log -1 --format="%H %s" # must be 831154c... "feat(auth): add Anclora Identity OIDC login as additional path" or a later commit that includes it
```

The migration file (`0003_add_identity_sub.py`) and the ORM model change
(`backend/auth/models.py`) must come from the exact commit being deployed to
production — do not run the migration from a different checkout than the one
about to be deployed.

## 5. Verify `ANCLORA_IDENTITY_ENABLED=false`

Before migrating:

```bash
# On the VPS / wherever the production backend env is loaded:
grep -c '^ANCLORA_IDENTITY_ENABLED=true' /home/toni/.config/anclora/runtime/purgedoc.env
# Expected output: 0 (the line is absent, or present and set to "false")
```

If this prints anything other than `0`, **stop** — OIDC must not be enabled
before this migration runs and login is re-verified.

## 6. Backup / recovery check

Neon provides continuous point-in-time recovery by default for its managed
databases; this repository does not maintain its own separate backup
mechanism. Before migrating:

- [ ] Confirm in the Neon console that point-in-time recovery is enabled for
      `anclora-purgedoc-db` and note the current timestamp as the recovery
      point to restore to if needed.
- [ ] This migration is additive and low-risk (see prior technical review),
      so a full logical backup is not required, but the PITR timestamp must
      still be noted before proceeding — this is the actual "backup or
      recovery check," not a rhetorical step.

## 7. Pre-migration schema inspection

```bash
cd backend
DATABASE_TARGET=production DATABASE_URL="<production connection string>" \
  python -c "
from sqlalchemy import create_engine, inspect
url = '<production connection string>'.replace('postgresql://', 'postgresql+psycopg://', 1)
engine = create_engine(url)
insp = inspect(engine)
cols = [c['name'] for c in insp.get_columns('users')]
print('users columns:', cols)
print('identity_sub already present:', 'identity_sub' in cols)
indexes = insp.get_indexes('users')
print('users indexes:', [i['name'] for i in indexes])
"
```

Expected: `identity_sub` is **not** in `cols`, and no `ix_users_identity_sub`
index exists yet. If either is already present, stop and investigate before
proceeding — the migration's own idempotent guard would skip in that case,
but an unexpected pre-existing column means something ran outside this
runbook and needs explanation first.

## 8. Exact migration command

```bash
cd backend
DATABASE_TARGET=production \
ALLOW_PRODUCTION_MIGRATIONS=true \
alembic upgrade head
```

This is the command inferred from `backend/alembic.ini`
(`script_location = alembic`, run from `backend/`) and `backend/alembic/env.py`
(`guard()` requiring both env vars; `database_url()` reading
`DATABASE_URL_UNPOOLED` or `DATABASE_URL`). `alembic upgrade head` will apply
only `0003_add_identity_sub` if the database is already at `0002_closed_access_auth`
— it does not re-run earlier revisions.

## 9. Differences from CleanSheet

- Down-revision differs: `0002_closed_access_auth` (PurgeDoc) vs.
  `0002_closed_access_whitelist` (CleanSheet) — cosmetic, not functional.
- Contract fields differ: CleanSheet's `.anclora/PRODUCTION_RUNTIME.md`
  declares `MIGRATION_CONFIRMATION_REQUIRED=true` explicitly; PurgeDoc's does
  not declare this field at all. As stated above, this runbook treats both
  identically regardless of that difference.
- Everything else (column, index, guard mechanism, command shape) is
  identical between the two apps.

## 10. Verify `alembic_version`

```bash
cd backend
DATABASE_TARGET=production ALLOW_PRODUCTION_MIGRATIONS=true alembic current
```

Expected output includes `0003_add_identity_sub (head)`.

## 11. Verify the nullable `users.identity_sub` column

```bash
cd backend
python -c "
from sqlalchemy import create_engine, inspect
url = '<production connection string>'.replace('postgresql://', 'postgresql+psycopg://', 1)
insp = inspect(create_engine(url))
col = next(c for c in insp.get_columns('users') if c['name'] == 'identity_sub')
print(col)
"
```

Expected: a column named `identity_sub`, type `VARCHAR(255)`,
`nullable: True`.

## 12. Verify the unique index

```bash
python -c "
from sqlalchemy import create_engine, inspect
url = '<production connection string>'.replace('postgresql://', 'postgresql+psycopg://', 1)
insp = inspect(create_engine(url))
print([i for i in insp.get_indexes('users') if i['name'] == 'ix_users_identity_sub'])
"
```

Expected: one index named `ix_users_identity_sub` with `unique: True` on
column `identity_sub`.

## 13. Verify no backfill occurred

```bash
python -c "
from sqlalchemy import create_engine, text
url = '<production connection string>'.replace('postgresql://', 'postgresql+psycopg://', 1)
with create_engine(url).connect() as conn:
    total = conn.execute(text('SELECT count(*) FROM users')).scalar()
    non_null = conn.execute(text('SELECT count(*) FROM users WHERE identity_sub IS NOT NULL')).scalar()
    print(f'total users: {total}, with identity_sub set: {non_null}')
"
```

Expected: `with identity_sub set: 0`. Any non-zero value means something wrote
to this column outside the OIDC callback path (which cannot have run yet,
since `ANCLORA_IDENTITY_ENABLED` is still `false`) — treat as an anomaly to
investigate, not proceed past.

## 14. Immediate test of existing local login

With `ANCLORA_IDENTITY_ENABLED` still `false`, perform one real login against
production using an existing whitelist-provisioned account (the dedicated
QA identity, `qa.identity@anclora.local`-style pattern per workspace policy —
never Toni's personal account):

```bash
curl -i -X POST https://api.purgedoc.anclora.com/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"<qa account email>","password":"<qa account password>"}'
```

Expected: `200 OK` with `access_token`/`refresh_token` cookies set, exactly as
before this migration. This is the direct verification for the critical
finding in the technical review (ORM query breakage risk) — a real request,
not just a schema check.

## 15. Confirm OIDC still disabled

Repeat step 5's check. It must still print `0`. The migration must not have
been bundled with an env change that flips this flag.

---

## 16. Rollback procedure

```bash
cd backend
DATABASE_TARGET=production \
ALLOW_PRODUCTION_MIGRATIONS=true \
alembic downgrade 0002_closed_access_auth
```

## 17. Rollback preconditions and risks

- [ ] Confirm no production code currently deployed references
      `identity_sub` (i.e., roll back the code deploy — revert to the commit
      before `831154c` — before or simultaneously with the schema rollback;
      rolling back the column while the ORM model still expects it recreates
      the exact breakage this runbook exists to prevent, just in reverse).
- [ ] Confirm `SELECT count(*) FROM users WHERE identity_sub IS NOT NULL` is
      `0`, or explicitly accept the loss of those linkages — `downgrade()`
      drops the column, which is destructive to any Identity-to-local-account
      link made in the meantime. If `ANCLORA_IDENTITY_ENABLED` was never
      turned on, this value will always be `0` and rollback is fully
      lossless.
- [ ] Risk: dropping `ix_users_identity_sub` then the column is two DDL
      statements; if the process is interrupted between them, the table is
      left with an unindexed nullable column and no unique constraint — not
      dangerous, but re-run `downgrade` to completion rather than leaving it
      partial.

## 18. Abort criteria

Abort (do not proceed to the next step) if:

- Step 2's resource-id check does not match `store_YVnSjBw8FknekSJt` exactly.
- Step 7 shows `identity_sub` or `ix_users_identity_sub` already present
  unexpectedly.
- Step 10 does not show `0003_add_identity_sub (head)` after running upgrade.
- Step 13 shows any non-zero `identity_sub` count before OIDC was ever
  enabled.
- Step 14's login test fails, returns an unexpected status code, or the
  response shape differs from pre-migration behavior.
- Step 15 shows `ANCLORA_IDENTITY_ENABLED` is unexpectedly `true`.

On any abort, do not proceed to code deploy or secret configuration; run the
rollback procedure only if the migration itself already partially applied and
needs to be undone — if it never applied, there is nothing to roll back.

## 19. Evidence to retain

- Full terminal output of steps 7 through 15 (schema inspection, `alembic
  current`, column/index verification, backfill check, login test response,
  flag check).
- The Neon PITR timestamp noted in step 6.
- The exact commit hash confirmed in step 4.
- Who ran the migration and the timestamp it was run.

Store this evidence in whatever internal record-keeping location Toni
designates for migration runs — this repository does not currently define
one, so do not assume `docs/` in this repo is the right place for it (it
should not contain live production evidence).

## 20. Responsible party and required authorization

- **Executor**: whoever Toni explicitly designates for this run — not
  assumed to be any specific role by this document.
- **Authorization required before step 8 (the actual migration command)**:
  1. Contract scope authorization — **done, 2026-09-27**:
     `.anclora/PRODUCTION_RUNTIME.md` now declares
     `PRODUCTION_MIGRATIONS_ALLOWED=true`, scoped to `0003_add_identity_sub`
     only (see the migration authorization log in that file, and the
     proposal document referenced above, marked ACCEPTED).
  2. Per-run confirmation — **still outstanding**: `MIGRATION_CONFIRMATION_REQUIRED=true`
     is now an explicit field in this repository's contract, and Toni's
     specific, dated confirmation for *this run* has not been given as of
     this writing. Step 1 above authorizes that the migration is contractually
     permitted; it does not itself constitute the per-run go-ahead.

This document describes the procedure to follow once the outstanding
per-run confirmation is given — it does not itself grant it.
