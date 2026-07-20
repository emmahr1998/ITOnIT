from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


def build_connection_url() -> str:
    """Build a SQL Server connection URL for SQLAlchemy + pyodbc."""
    driver = quote_plus(settings.DATABASE_DRIVER)

    if settings.DATABASE_USERNAME and settings.DATABASE_PASSWORD:
        credentials = f"{quote_plus(settings.DATABASE_USERNAME)}:{quote_plus(settings.DATABASE_PASSWORD)}"
        auth_params = ""
    else:
        # No credentials supplied: fall back to Windows Trusted Connection.
        credentials = ""
        auth_params = "&trusted_connection=yes"

    return (
        f"mssql+pyodbc://{credentials}@{settings.DATABASE_SERVER}/{settings.DATABASE_NAME}"
        f"?driver={driver}{auth_params}"
    )


# create_engine() only prepares the connection pool; it does not connect
# to SQL Server until a session actually executes a query. This means the
# app can start even if the database is not reachable yet.
engine = create_engine(build_connection_url())

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class every ORM model will inherit from."""

    pass


def get_db() -> Session:
    """FastAPI dependency that yields a database session and closes it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
