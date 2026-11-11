from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import get_settings

_settings = get_settings()

engine = create_engine(
    f"postgresql+psycopg2://{_settings.db_user}:{_settings.db_password}"
    f"@{_settings.db_host}:{_settings.db_port}/{_settings.db_name}",
    pool_pre_ping=True,
    pool_recycle=3600,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
