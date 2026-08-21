"""Message repository."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.entities import Message
from ..mappers import channel_to_entity, message_to_entity, message_to_model
from ..models import ChannelModel, MessageModel


class SqlMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _channel(self, channel_id: str):
        return await self.session.get(ChannelModel, channel_id)

    async def get(self, message_id: str) -> Message | None:
        m = await self.session.get(MessageModel, message_id)
        if not m:
            return None
        ch = await self.session.get(ChannelModel, m.channel_id)
        if not ch:
            return None
        return message_to_entity(m, channel_to_entity(ch))

    async def get_by_channel_and_tmid(
        self, channel_id: str, telegram_message_id: int
    ) -> Message | None:
        stmt = select(MessageModel).where(
            MessageModel.channel_id == channel_id,
            MessageModel.telegram_message_id == telegram_message_id,
        )
        res = await self.session.execute(stmt)
        m = res.scalar_one_or_none()
        if not m:
            return None
        ch = await self.session.get(ChannelModel, m.channel_id)
        if not ch:
            return None
        return message_to_entity(m, channel_to_entity(ch))

    async def find_by_text_hash(self, text_hash: str) -> list[Message]:
        stmt = select(MessageModel).where(MessageModel.text_hash == text_hash)
        res = await self.session.execute(stmt)
        out: list[Message] = []
        for m in res.scalars().all():
            ch = await self.session.get(ChannelModel, m.channel_id)
            if ch:
                out.append(message_to_entity(m, channel_to_entity(ch)))
        return out

    async def add(self, message: Message) -> None:
        existing = await self.session.get(MessageModel, message.id)
        if existing is not None:
            return
        self.session.add(message_to_model(message, message.text_hash()))

    async def list_recent_for_channel(
        self, channel_id: str, since: datetime | None
    ) -> list[Message]:
        stmt = select(MessageModel).where(MessageModel.channel_id == channel_id)
        if since is not None:
            stmt = stmt.where(MessageModel.posted_at >= since)
        stmt = stmt.order_by(MessageModel.posted_at.desc())
        res = await self.session.execute(stmt)
        ch = await self.session.get(ChannelModel, channel_id)
        if not ch:
            return []
        ce = channel_to_entity(ch)
        return [message_to_entity(m, ce) for m in res.scalars().all()]
