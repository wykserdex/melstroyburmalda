"""Outreach repository."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.enums import OutreachStatus
from ..mappers import outreach_to_entity, outreach_to_model
from ..models import ContactModel, LeadModel, OutreachModel
from .contacts import SqlContactRepository
from .leads import SqlLeadRepository


class SqlOutreachRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._lead_repo = SqlLeadRepository(session)
        self._contact_repo = SqlContactRepository(session)

    async def _resolve(self, m: OutreachModel):
        lmod = await self.session.get(LeadModel, m.lead_id)
        cmod = await self.session.get(ContactModel, m.contact_id)
        if not lmod or not cmod:
            return None
        lead = await self._lead_repo.get(lmod.id)
        contact = await self._contact_repo.get(cmod.id)
        if not lead or not contact:
            return None
        return outreach_to_entity(m, lead, contact)

    async def get(self, outreach_id: str):
        m = await self.session.get(OutreachModel, outreach_id)
        if not m:
            return None
        return await self._resolve(m)

    async def add(self, outreach) -> None:
        existing = await self.session.get(OutreachModel, outreach.id)
        if existing is not None:
            return
        self.session.add(outreach_to_model(outreach))

    async def update_status(
        self,
        outreach_id: str,
        status: OutreachStatus,
        *,
        sent_message_id: int | None = None,
        approved_by: str | None = None,
        approval_reason: str | None = None,
        at: datetime | None = None,
    ) -> None:
        values: dict = {"status": status.value}
        if status == OutreachStatus.SENT:
            values["sent_at"] = at or datetime.utcnow()
            if sent_message_id is not None:
                values["sent_message_id"] = sent_message_id
        if status == OutreachStatus.APPROVED:
            values["approved_at"] = at or datetime.utcnow()
            if approved_by is not None:
                values["approved_by"] = approved_by
            if approval_reason is not None:
                values["approval_reason"] = approval_reason
        stmt = update(OutreachModel).where(OutreachModel.id == outreach_id).values(**values)
        await self.session.execute(stmt)

    async def list_by_status(self, status: OutreachStatus) -> list:
        stmt = select(OutreachModel).where(OutreachModel.status == status.value)
        res = await self.session.execute(stmt)
        out = []
        for m in res.scalars().all():
            o = await self._resolve(m)
            if o:
                out.append(o)
        return out

    async def get_by_idempotency_key(self, key: str):
        stmt = select(OutreachModel).where(OutreachModel.idempotency_key == key)
        res = await self.session.execute(stmt)
        m = res.scalar_one_or_none()
        if not m:
            return None
        return await self._resolve(m)
