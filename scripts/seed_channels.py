"""Seed a few channels manually.

Usage:
    python -m scripts.seed_channels
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from telegram_outreach.bootstrap import build
from telegram_outreach.config.settings import get_settings
from telegram_outreach.domain.entities import Channel
from telegram_outreach.domain.enums import ChannelSource


async def main() -> None:
    settings = get_settings()
    container = build(settings)
    seed = [
        Channel(
            id="seed_1",
            telegram_id=1234567890,
            username="example_jobs",
            title="Example Jobs",
            description="",
            subscribers=2000,
            source=ChannelSource.SEED,
        ),
    ]
    async with container.uow_factory() as uow:  # type: ignore[arg-type]
        assert uow.channels is not None
        for ch in seed:
            existing = await uow.session.execute(
                select(type(seed[0])).where(  # type: ignore[arg-type]
                    __import__("telegram_outreach.infrastructure.persistence.models", fromlist=["ChannelModel"]).ChannelModel.telegram_id
                    == ch.telegram_id
                )
            )
            if existing.scalar_one_or_none() is None:
                await uow.channels.add(ch)
        await uow.commit()


if __name__ == "__main__":
    asyncio.run(main())
