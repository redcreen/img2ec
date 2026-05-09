from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from img2ec.config import get_settings

_settings = get_settings()
engine = create_engine(_settings.db_url, echo=False, connect_args={"check_same_thread": False} if _settings.db_url.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
