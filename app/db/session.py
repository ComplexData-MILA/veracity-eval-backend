from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL, pool_pre_ping=True, pool_size=20, max_overflow=10, pool_timeout=30, pool_recycle=1800
)

# Create session factory
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session() -> Generator[Session, None, None]:
    """
    Get a database session.

    Yields:
        Session: The database session

    Example:
        with next(get_session()) as session:
            result = session.query(User).all()
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
