from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.settings import get_settings


class Base(DeclarativeBase):
    pass


def build_engine(url: str | None = None):
    database_url = url or get_settings().database_url
    kwargs = {"connect_args": {"check_same_thread": False}} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, pool_pre_ping=True, **kwargs)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

