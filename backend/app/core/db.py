from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_timeout=5,
    connect_args={"connect_timeout": 5} if settings.database_url.startswith("postgresql") else {},
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_connection() -> bool:
    with engine.connect() as connection:
        if connection.dialect.name == "postgresql":
            connection.execute(text("SET LOCAL statement_timeout = 3000"))
        connection.execute(text("SELECT 1"))
    return True
