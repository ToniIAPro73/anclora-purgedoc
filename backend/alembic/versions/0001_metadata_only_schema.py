"""Create the metadata-only PurgeDoc persistence boundary."""
from alembic import op
import sqlalchemy as sa

revision = "0001_metadata_only_schema"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    from db.models import Base
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names(schema="public"))
    unexpected = existing - set(Base.metadata.tables) - {"alembic_version"}
    if unexpected:
        raise RuntimeError(f"Unexpected public tables; refusing PurgeDoc migration: {sorted(unexpected)}")
    Base.metadata.create_all(bind=bind, checkfirst=True)

def downgrade():
    raise RuntimeError("PurgeDoc metadata schema is forward-only; destructive downgrade is forbidden")
