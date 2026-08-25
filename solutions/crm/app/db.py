from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data" / "crm.db"


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    raw = os.environ.get("CRM_DATABASE_URL")
    if raw:
        return raw
    DEFAULT_DB.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_DB}"


def make_engine(url: str | None = None):
    url = url or database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    if url.startswith("sqlite") and ":memory:" in url:
        return create_engine(
            url,
            connect_args=connect_args,
            poolclass=StaticPool,
            future=True,
        )
    return create_engine(url, connect_args=connect_args, future=True)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_engine():
    return SessionLocal.kw.get("bind") or engine


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def reset_engine(url: str) -> None:
    """Used by hidden tests so they never touch the seed file."""
    global engine
    engine = make_engine(url)
    SessionLocal.configure(bind=engine)
