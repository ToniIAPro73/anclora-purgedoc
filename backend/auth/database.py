import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url and url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    if not url:
        url = "sqlite:////tmp/purgedoc_auth.db"
    return url

_db_url = get_database_url()
_is_sqlite = _db_url.startswith("sqlite")

if _is_sqlite:
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        _db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    try:
        from backend.db.models import Base
        from backend.auth.models import AuthBase
        Base.metadata.create_all(bind=engine)
        AuthBase.metadata.create_all(bind=engine)
    except Exception:
        pass

else:
    engine = create_engine(_db_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
