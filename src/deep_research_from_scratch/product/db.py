"""Database setup for the product API."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from deep_research_from_scratch.product.config import settings


engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base declarative class for all models."""


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for request handling."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
