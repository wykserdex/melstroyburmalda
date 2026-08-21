"""Conversation repository."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.entities import Conversation
from ....domain.enums import ConversationStatus
from ..mappers import conversation_to_entity
from ..models import ContactModel, ConversationMessageModel, ConversationModel, OutreachModel
from .contacts import SqlContactRepository
from .outreach import SqlOutreachRepository


class SqlConversationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._outreach_repo = SqlOutreachRepository(session)
        self._contact_repo = SqlContactRepository(session)

    async def _resolve(self, m: ConversationModel):
        outreach_m = await self.session.get(OutreachModel, m.outreach_id)
        contact_m = await self.session.get(ContactModel, m.contact_id)
        if not outreach_m or not contact_m:
            return None
        outreach = await self._outreach_repo.get(outreach_m.id)
        contact = await self._contact_repo.get(contact_m.id)
        if not outreach or not contact:
            return None
        return conversation_to_entity(m, outreach, contact)

    async def get(self, conversation_id: str) -> Conversation | None:
        m = await self.session.get(ConversationModel, conversation_id)
        if not m:
            return None
        return await self._resolve(m)

    async def get_by_outreach(self, outreach_id: str) -> Conversation | None:
        stmt = select(ConversationModel).where(ConversationModel.outreach_id == outreach_id)
        res = await self.session.execute(stmt)
        m = res.scalar_one_or_none()
        if not m:
            return None
        return await self._resolve(m)

    async def add(self, conversation: Conversation) -> None:
        existing = await self.session.get(ConversationModel, conversation.id)
        if existing is not None:
            return
        self.session.add(
            ConversationModel(
                id=conversation.id,
                outreach_id=conversation.outreach.id,
                contact_id=conversation.contact.id,
                status=conversation.status.value,
                last_message_at=conversation.last_message_at,
                next_followup_at=conversation.next_followup_at,
                followup_attempts=conversation.followup_attempts,
                created_at=conversation.created_at,
                closed_at=conversation.closed_at,
                meta=conversation.metadata,
            )
        )

    async def update_status(
        self,
        conversation_id: str,
        status: ConversationStatus,
        *,
        next_followup_at: datetime | None = None,
        at: datetime | None = None,
    ) -> None:
        values: dict = {"status": status.value}
        if next_followup_at is not None:
            values["next_followup_at"] = next_followup_at
        if status == ConversationStatus.CLOSED:
            values["closed_at"] = at or datetime.utcnow()
        stmt = (
            update(ConversationModel)
            .where(ConversationModel.id == conversation_id)
            .values(**values)
        )
        await self.session.execute(stmt)

    async def add_message(
        self,
        conversation_id: str,
        direction: str,
        text: str,
        telegram_message_id: int | None,
        posted_at: datetime,
    ) -> None:
        self.session.add(
            ConversationMessageModel(
                conversation_id=conversation_id,
                direction=direction,
                text=text,
                telegram_message_id=telegram_message_id,
                posted_at=posted_at,
                meta={},
            )
        )
        await self.session.execute(
            update(ConversationModel)
            .where(ConversationModel.id == conversation_id)
            .values(last_message_at=posted_at)
        )

    async def list_due_followups(self, now: datetime) -> list[Conversation]:
        stmt = (
            select(ConversationModel)
            .where(
                ConversationModel.next_followup_at.is_not(None),
                ConversationModel.next_followup_at <= now,
                ConversationModel.status.in_(
                    [
                        ConversationStatus.FOLLOWUP_SCHEDULED.value,
                        ConversationStatus.WAITING_REPLY.value,
                    ]
                ),
            )
        )
        res = await self.session.execute(stmt)
        out = []
        for m in res.scalars().all():
            conv = await self._resolve(m)
            if conv:
                out.append(conv)
        return out
