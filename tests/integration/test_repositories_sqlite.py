"""Integration tests for SQLAlchemy repositories using in-memory SQLite."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from telegram_outreach.domain.entities import Channel
from telegram_outreach.domain.entities.message import Message
from telegram_outreach.domain.enums import ChannelSource
from telegram_outreach.infrastructure.persistence.models import Base
from telegram_outreach.infrastructure.persistence.repositories import (
    SqlChannelRepository,
    SqlMessageRepository,
)


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    yield sm
    await engine.dispose()


@pytest.mark.asyncio
async def test_channel_repo_upsert_and_query(session_factory) -> None:
    ch = Channel(
        id="ch1",
        telegram_id=100,
        username="foo",
        title="Foo",
        description="",
        subscribers=500,
    )
    async with session_factory() as s:
        repo = SqlChannelRepository(s)
        await repo.add(ch)
        await s.commit()
    async with session_factory() as s:
        repo = SqlChannelRepository(s)
        got = await repo.get_by_telegram_id(100)
        assert got is not None
        assert got.username == "foo"


@pytest.mark.asyncio
async def test_message_unique_constraint(session_factory) -> None:
    ch = Channel(
        id="ch1", telegram_id=100, username=None, title="x", description="", subscribers=1
    )
    async with session_factory() as s:
        ch_repo = SqlChannelRepository(s)
        msg_repo = SqlMessageRepository(s)
        await ch_repo.add(ch)
        m1 = Message(
            id="m1",
            channel=ch,
            telegram_message_id=10,
            text="hi",
            posted_at=datetime.now(timezone.utc),
        )
        await msg_repo.add(m1)
        await s.commit()
        # Same id, different row — should not duplicate
        m1b = Message(
            id="m1",
            channel=ch,
            telegram_message_id=10,
            text="hi",
            posted_at=datetime.now(timezone.utc),
        )
        await msg_repo.add(m1b)
        await s.commit()
        msgs = await msg_repo.list_recent_for_channel("ch1", None)
        assert len(msgs) == 1
