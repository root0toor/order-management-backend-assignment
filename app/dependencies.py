from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Session:
    """
    Dependency injection for database session.
    
    Yields a session for the request lifecycle, ensures cleanup.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
