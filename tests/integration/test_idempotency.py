"""Idempotency repository tests."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from telegram_outreach.domain.enums import IdempotencyState
from telegram_outreach.domain.value_objects import IdempotencyKey
from telegram_outreach.infrastructure.persistence.models import Base
from telegram_outreach.infrastructure.persistence.repositories import (
    SqlIdempotencyRepository,
)


@pytest.fixture
async def sm():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.mark.asyncio
async def test_create_pending_returns_true_once(sm) -> None:
    key = IdempotencyKey(key="k12345678")
    async with sm() as s:
        repo = SqlIdempotencyRepository(s)
        ok = await repo.create_pending(key, "outreach", "o1")
        assert ok
        await s.commit()
    async with sm() as s:
        repo = SqlIdempotencyRepository(s)
        ok = await repo.create_pending(key, "outreach", "o1")
        assert not ok


@pytest.mark.asyncio
async def test_mark_completed(sm) -> None:
    key = IdempotencyKey(key="k12345678")
    async with sm() as s:
        repo = SqlIdempotencyRepository(s)
        await repo.create_pending(key, "outreach", "o1")
        await s.commit()
        await repo.mark_completed(key.key, "o1")
        await s.commit()
    async with sm() as s:
        repo = SqlIdempotencyRepository(s)
        got = await repo.get(key.key)
        assert got is not None
        assert got[0] == IdempotencyState.COMPLETED
        assert got[1] == "o1"
