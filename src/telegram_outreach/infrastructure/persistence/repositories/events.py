"""Event log repository."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.entities import EventLogEntry
from ....domain.enums import EventType
from ..mappers import event_to_entity, event_to_model
from ..models import EventLogModel


class SqlEventLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(self, entry: EventLogEntry) -> None:
        existing = await self.session.get(EventLogModel, entry.id)
        if existing is not None:
            return
        self.session.add(event_to_model(entry))
        await self.session.flush()

    async def list_for_entity(
        self, entity_type: str, entity_id: str
    ) -> list[EventLogEntry]:
        stmt = (
            select(EventLogModel)
            .where(
                EventLogModel.entity_type == entity_type,
                EventLogModel.entity_id == entity_id,
            )
            .order_by(EventLogModel.created_at.asc())
        )
        res = await self.session.execute(stmt)
        return [event_to_entity(m) for m in res.scalars().all()]

    async def list_by_type(
        self, event_type: EventType, limit: int = 100
    ) -> list[EventLogEntry]:
        stmt = (
            select(EventLogModel)
            .where(EventLogModel.event_type == event_type.value)
            .order_by(EventLogModel.created_at.desc())
            .limit(limit)
        )
        res = await self.session.execute(stmt)
        return [event_to_entity(m) for m in res.scalars().all()]
