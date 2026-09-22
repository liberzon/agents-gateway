from typing import Generator

from sqlalchemy.engine import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from db.url import get_db_url

# Create SQLAlchemy Engine using a database URL
db_url: str = get_db_url()
# Supabase's SESSION-mode pooler caps this project at 15 clients
# ("FATAL: (EMAXCONNSESSION) max clients reached ... pool_size: 15"). SQLAlchemy's
# defaults (pool_size 5 + max_overflow 10) would spend all 15 on this one engine, and
# agno's PostgresDb used to open another engine per agent on top of that — which
# exhausted the pooler and made every session write fail, so chat history silently
# vanished and agents kept re-asking for context. One bounded pool, shared by the API
# and by every agent's PostgresDb (see agents.agent).
db_engine: Engine = create_engine(
    db_url,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=3,
    pool_recycle=300,
    pool_timeout=10,
)

# Create a SessionLocal class
SessionLocal: sessionmaker[Session] = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency to get a database session.

    Yields:
        Session: An SQLAlchemy database session.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
