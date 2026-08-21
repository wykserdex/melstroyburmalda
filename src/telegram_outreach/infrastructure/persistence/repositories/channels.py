"""Channel repository — SQLAlchemy implementation."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.entities import Channel
from ..mappers import channel_to_entity, channel_to_model
from ..models import ChannelModel


class SqlChannelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, channel_id: str) -> Channel | None:
        m = await self.session.get(ChannelModel, channel_id)
        return channel_to_entity(m) if m else None

    async def get_by_telegram_id(self, telegram_id: int) -> Channel | None:
        stmt = select(ChannelModel).where(ChannelModel.telegram_id == telegram_id)
        res = await self.session.execute(stmt)
        m = res.scalar_one_or_none()
        return channel_to_entity(m) if m else None

    async def list_active(self) -> list[Channel]:
        stmt = select(ChannelModel).where(ChannelModel.is_active.is_(True))
        res = await self.session.execute(stmt)
        return [channel_to_entity(m) for m in res.scalars().all()]

    async def add(self, channel: Channel) -> None:
        existing = await self.session.get(ChannelModel, channel.id)
        if existing is not None:
            # upsert by id; preserve last_scanned_at
            new = channel_to_model(channel)
            for col in (
                "telegram_id",
                "username",
                "title",
                "description",
                "subscribers",
                "source",
                "is_active",
                "meta",
            ):
                setattr(existing, col, getattr(new, col))
        else:
            self.session.add(channel_to_model(channel))

    async def update_last_scanned(self, channel_id: str, at: datetime) -> None:
        stmt = update(ChannelModel).where(ChannelModel.id == channel_id).values(last_scanned_at=at)
        await self.session.execute(stmt)
