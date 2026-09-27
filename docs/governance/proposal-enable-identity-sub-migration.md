# Proposal — Authorize the `identity_sub` Migration Against Production

Status: **ACCEPTED (Scoped model) — 2026-09-27**. `.anclora/PRODUCTION_RUNTIME.md`
now reads `PRODUCTION_MIGRATIONS_ALLOWED=true`, limited to
`0003_add_identity_sub` only, plus a new `MIGRATION_CONFIRMATION_REQUIRED=true`
field (this repository had none before). See the "Scoped migration
authorization (active)" section and the migration authorization log table in
that file for the authoritative, current record. This proposal document is
kept as the historical rationale for that change, not re-edited to match —
the contract file, not this proposal, is the source of truth going forward.

**This acceptance does not itself authorize running the migration.** Applying
`0003_add_identity_sub` still requires satisfying
`MIGRATION_CONFIRMATION_REQUIRED=true` for this specific execution, following
`docs/deployment/migration-identity-sub-runbook.md`, and remains entirely
separate from `ANCLORA_IDENTITY_ENABLED` (still `false`) and from any
deployment action.

## What is being requested

A one-time, explicit authorization to run
`backend/alembic/versions/0003_add_identity_sub.py`
(`alembic upgrade head`) against the production Neon database
(`anclora-purgedoc-db`, resource id `store_YVnSjBw8FknekSJt`), following the
procedure in `docs/deployment/migration-identity-sub-runbook.md`.

## Proposed contract change (if approved)

In `.anclora/PRODUCTION_RUNTIME.md`, under "Database Migration Contract":

```diff
- PRODUCTION_MIGRATIONS_ALLOWED=false
+ PRODUCTION_MIGRATIONS_ALLOWED=true
```

Two implementation choices for Toni to pick between, not decided here:

1. **Scoped**: flip it to `true` only for the duration of this specific
   migration, then flip it back to `false` immediately after, treating each
   future migration as requiring the same explicit round-trip.
2. **Standing**: flip it to `true` permanently now that the closed-access
   auth schema (introduced 2026-09-24) is an established, evolving part of
   this repository, and rely on the per-run confirmation discipline
   described in the runbook (Section 20) as the actual gate going forward,
   rather than toggling this flag every time.

This proposal does not recommend one over the other — it depends on how much
day-to-day migration friction Toni wants versus how much the flag itself
should mean "there is an active migration in flight right now."

## Why this is being proposed now rather than assumed

- `PRODUCTION_MIGRATIONS_ALLOWED=false` was set on 2026-09-23, one day before
  the closed-access auth feature (with its own `users`/`auth_whitelist`
  schema) shipped — this repository's own `.anclora/PRODUCTION_RUNTIME.md`
  already carries a correction note (added alongside the Wave 1 OIDC work)
  acknowledging that the "no user accounts or authentication exist" line was
  stale. This flag was very likely set with document-metadata-only tables in
  mind, before there was any auth schema to migrate at all.
- No migration has ever been run against this repository's production
  database since the auth schema shipped (only `0001` and `0002`, both
  presumably applied together with the initial closed-access rollout — not
  verified here, this proposal does not assume their history beyond what's
  in version control).

## What is NOT being proposed

- No change to `MIGRATION_SYSTEM=Alembic`.
- No change to how migrations are written or reviewed going forward — this
  is specifically about authorizing this one migration (and, if "Standing"
  is chosen, migrations of this shape in general), not a broader process
  change.
- No change to `DATABASE_RUNTIME_SCOPE=metadata_only` or any other
  declaration in this file unrelated to migration authorization.

## Decision needed from Toni

- Approve or reject running this migration at all.
- If approved: Scoped or Standing authorization model (see above).
- Confirm the specific runbook (`docs/deployment/migration-identity-sub-runbook.md`)
  is the procedure to follow.
