from collections.abc import Generator

from sqlalchemy.orm import Session

from app.db.database import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Yield one SQLAlchemy session for the lifetime of a single request.

    FastAPI caches the result of a yield-dependency per request, so every
    route (and every repository it uses) that depends on this shares the
    same session, then it is closed once the request finishes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
