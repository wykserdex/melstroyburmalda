"""Async SQLAlchemy engine + session factory.

The engine is created lazily so that tests can swap it. A single AsyncSession
is used per unit-of-work; never share a session across use cases.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ...config.settings import Settings
from .models import Base


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def _create_engine(settings: Settings) -> AsyncEngine:
    url = settings.database_url
    connect_args: dict[str, Any] = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
    return create_async_engine(
        url,
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )


def init_engine(settings: Settings) -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        _engine = _create_engine(settings)
        _sessionmaker = async_sessionmaker(
            _engine, expire_on_commit=False, class_=AsyncSession
        )
    return _engine


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("DB engine not initialised. Call init_engine(settings) first.")
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        raise RuntimeError("DB engine not initialised. Call init_engine(settings) first.")
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    """Async context manager that yields a session and commits/rolls back."""
    sm = get_sessionmaker()
    async with sm() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all() -> None:
    """For dev / tests. Production uses Alembic."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
