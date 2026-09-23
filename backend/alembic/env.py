import asyncio
import os
import sys
from logging.config import fileConfig
from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy import pool
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from db.models import Base  # noqa: E402

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
target_metadata = Base.metadata

def database_url():
    url = os.environ.get("DATABASE_URL_UNPOOLED") or os.environ.get("DATABASE_URL")
    if url and url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

def guard():
    if os.environ.get("DATABASE_TARGET", "local").lower() == "production" and os.environ.get("ALLOW_PRODUCTION_MIGRATIONS") != "true":
        raise RuntimeError("Refusing production migration: set ALLOW_PRODUCTION_MIGRATIONS=true explicitly")
    if not database_url():
        raise RuntimeError("DATABASE_URL is required for PurgeDoc migrations")

def run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()

async def run_online():
    guard()
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = database_url()
    engine = async_engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(run_migrations)
    await engine.dispose()

if context.is_offline_mode():
    guard()
    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(run_online())
