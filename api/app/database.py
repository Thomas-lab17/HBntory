# Database setup: engine, session factory, and declarative Base.
# SQLite for development; SQLAlchemy makes switching to Postgres easy later.
import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

# Overridable so the Docker container can point at a persistent volume.
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./hbntory.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


@event.listens_for(engine, "connect")
def _enable_sqlite_fk(dbapi_conn, _record):
    """Turn on foreign-key enforcement for SQLite (off by default)."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
