"""Add users.identity_sub for Anclora Identity OIDC account linking (additive only).

Revision ID: 0003_add_identity_sub
Revises: 0002_closed_access_auth
Create Date: 2026-09-27

NOT APPLIED TO PRODUCTION AS PART OF THIS CHANGE. PurgeDoc's own
.anclora/PRODUCTION_RUNTIME.md declares PRODUCTION_MIGRATIONS_ALLOWED=false.
This migration is prepared and reviewed but requires an explicit,
separate authorization from Toni (and a correction of that stale
PRODUCTION_RUNTIME.md line, which predates the whitelist auth feature by one
day and still incorrectly reads "no user accounts or authentication exist")
before `alembic upgrade` is run against the production database.

Purely additive: adds one nullable, unique column. No existing column is
altered or dropped, so it is backward-compatible with the currently deployed
code (which does not reference `identity_sub`) for the entire rollout window.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_add_identity_sub"
down_revision = "0002_closed_access_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {c["name"] for c in inspector.get_columns("users")}

    if "identity_sub" not in existing_columns:
        op.add_column("users", sa.Column("identity_sub", sa.String(255), nullable=True))
        op.create_index("ix_users_identity_sub", "users", ["identity_sub"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {c["name"] for c in inspector.get_columns("users")}

    if "identity_sub" in existing_columns:
        op.drop_index("ix_users_identity_sub", table_name="users")
        op.drop_column("users", "identity_sub")
