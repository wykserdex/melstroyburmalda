"""Lead repository."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.enums import LeadStatus
from ..mappers import lead_to_entity, lead_to_model
from ..models import ContactModel, LeadModel, VacancyModel
from .contacts import SqlContactRepository
from .vacancies import SqlVacancyRepository


class SqlLeadRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._vacancy_repo = SqlVacancyRepository(session)
        self._contact_repo = SqlContactRepository(session)

    async def _resolve(self, m: LeadModel):
        vmod = await self.session.get(VacancyModel, m.vacancy_id)
        cmod = await self.session.get(ContactModel, m.contact_id)
        if not vmod or not cmod:
            return None
        vacancy = await self._vacancy_repo.get(vmod.id)
        contact = await self._contact_repo.get(cmod.id)
        if not vacancy or not contact:
            return None
        return lead_to_entity(m, vacancy, contact)

    async def get(self, lead_id: str):
        m = await self.session.get(LeadModel, lead_id)
        if not m:
            return None
        return await self._resolve(m)

    async def add(self, lead) -> None:
        existing = await self.session.get(LeadModel, lead.id)
        if existing is not None:
            # Upsert mutable fields (status, score, reason, meta)
            existing.status = lead.status.value
            existing.score = lead.score.value
            existing.reason = lead.reason
            existing.meta = lead.metadata
            return
        self.session.add(lead_to_model(lead))

    async def get_by_vacancy_contact(self, vacancy_id: str, contact_id: str):
        stmt = select(LeadModel).where(
            LeadModel.vacancy_id == vacancy_id, LeadModel.contact_id == contact_id
        )
        res = await self.session.execute(stmt)
        m = res.scalar_one_or_none()
        if not m:
            return None
        return await self._resolve(m)

    async def list_by_status(self, status: LeadStatus) -> list:
        stmt = select(LeadModel).where(LeadModel.status == status.value)
        res = await self.session.execute(stmt)
        out = []
        for m in res.scalars().all():
            lead = await self._resolve(m)
            if lead:
                out.append(lead)
        return out

    async def list_for_vacancy(self, vacancy_id: str) -> list:
        stmt = select(LeadModel).where(LeadModel.vacancy_id == vacancy_id)
        res = await self.session.execute(stmt)
        out = []
        for m in res.scalars().all():
            lead = await self._resolve(m)
            if lead:
                out.append(lead)
        return out
