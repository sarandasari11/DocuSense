import os
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text
from app.config import settings

# Create database engine
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, echo=False, connect_args=connect_args)

def init_db():
    """Prepare storage and create development tables.

    Production schemas are managed by Alembic and must be migrated before startup.
    """
    os.makedirs(settings.STORAGE_DIR, exist_ok=True)
    if settings.QDRANT_USE_LOCAL_STORAGE and settings.QDRANT_PATH:
        os.makedirs(settings.QDRANT_PATH, exist_ok=True)
    if settings.APP_ENV != "production":
        SQLModel.metadata.create_all(engine)


def check_database() -> dict:
    """Return a small, safe database connectivity status for readiness checks."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"status": "ok", "backend": engine.url.get_backend_name()}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}

def get_session():
    """Dependency for obtaining DB session."""
    with Session(engine) as session:
        yield session
