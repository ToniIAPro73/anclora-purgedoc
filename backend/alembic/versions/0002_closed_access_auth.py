"""Create closed access auth tables (users, auth_whitelist, auth_audit_events, session_owners).

Revision ID: 0002_closed_access_auth
Revises: 0001_metadata_only_schema
Create Date: 2026-09-24
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_closed_access_auth"
down_revision = "0001_metadata_only_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names(schema="public" if is_postgres else None))

    # 1. users table
    if "users" not in existing_tables:
        op.create_table(
            "users",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False, unique=True),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("display_name", sa.String(255), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_users_email", "users", ["email"], unique=True)
        op.create_index("ix_users_status", "users", ["status"])

    # 2. auth_whitelist table
    if "auth_whitelist" not in existing_tables:
        op.create_table(
            "auth_whitelist",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("email", sa.String(255), nullable=False, unique=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
            sa.Column("token_hash", sa.String(64), nullable=True, unique=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True),
            sa.Column("created_by", sa.String(255), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_auth_whitelist_email", "auth_whitelist", ["email"], unique=True)
        op.create_index("ix_auth_whitelist_status", "auth_whitelist", ["status"])
        op.create_index("ix_auth_whitelist_token_hash", "auth_whitelist", ["token_hash"], unique=True)
        op.create_index("ix_auth_whitelist_expires_at", "auth_whitelist", ["expires_at"])
        op.create_index("ix_auth_whitelist_user_id", "auth_whitelist", ["user_id"], unique=True)

    # 3. auth_audit_events table
    if "auth_audit_events" not in existing_tables:
        json_type = postgresql.JSONB if is_postgres else sa.JSON
        op.create_table(
            "auth_audit_events",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("event", sa.String(50), nullable=False),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("user_id", sa.String(36), nullable=True),
            sa.Column("metadata_json", json_type, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_auth_audit_events_event", "auth_audit_events", ["event"])
        op.create_index("ix_auth_audit_events_email", "auth_audit_events", ["email"])
        op.create_index("ix_auth_audit_events_user_id", "auth_audit_events", ["user_id"])
        op.create_index("ix_auth_audit_events_created_at", "auth_audit_events", ["created_at"])

    # 4. session_owners table
    if "session_owners" not in existing_tables:
        op.create_table(
            "session_owners",
            sa.Column("session_id", sa.String(128), sa.ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_session_owners_user_id", "session_owners", ["user_id"])


def downgrade() -> None:
    raise RuntimeError("PurgeDoc schema is forward-only; destructive downgrade is forbidden")
