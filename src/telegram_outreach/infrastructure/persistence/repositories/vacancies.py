"""Vacancy repository."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.enums import VacancyStatus
from ..mappers import (
    channel_to_entity,
    contact_to_entity,
    message_to_entity,
    vacancy_to_entity,
    vacancy_to_model,
)
from ..models import ChannelModel, ContactModel, MessageModel, VacancyModel


class SqlVacancyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, vacancy_id: str):
        m = await self.session.get(VacancyModel, vacancy_id)
        if not m:
            return None
        msg_m = await self.session.get(MessageModel, m.message_id)
        ch_m = await self.session.get(ChannelModel, m.channel_id)
        if not msg_m or not ch_m:
            return None
        contact = None
        if m.contact_hint_user_id or m.contact_hint_username:
            contact = await self._resolve_hint(m.contact_hint_user_id, m.contact_hint_username)
        return vacancy_to_entity(
            m,
            message_to_entity(msg_m, channel_to_entity(ch_m)),
            contact,
        )

    async def _resolve_hint(self, user_id, username):
        if user_id:
            stmt = select(ContactModel).where(ContactModel.user_id == user_id)
            res = await self.session.execute(stmt)
            row = res.scalar_one_or_none()
            if row:
                return contact_to_entity(row)
        if username:
            stmt = select(ContactModel).where(ContactModel.username == username)
            res = await self.session.execute(stmt)
            row = res.scalar_one_or_none()
            if row:
                return contact_to_entity(row)
        return None

    async def add(self, vacancy) -> None:
        existing = await self.session.get(VacancyModel, vacancy.id)
        if existing is not None:
            existing.status = vacancy.status.value
            existing.title = vacancy.title
            existing.description = vacancy.description
            existing.requirements = vacancy.requirements
            existing.meta = vacancy.metadata
            return
        self.session.add(vacancy_to_model(vacancy))

    async def update_status(
        self, vacancy_id: str, status: VacancyStatus, at: datetime | None = None
    ) -> None:
        values: dict = {"status": status.value}
        if status == VacancyStatus.PARSED:
            values["parsed_at"] = at or datetime.utcnow()
        if status == VacancyStatus.CLOSED:
            values["closed_at"] = at or datetime.utcnow()
        stmt = update(VacancyModel).where(VacancyModel.id == vacancy_id).values(**values)
        await self.session.execute(stmt)

    async def list_by_status(self, status: VacancyStatus) -> list:
        stmt = select(VacancyModel).where(VacancyModel.status == status.value)
        res = await self.session.execute(stmt)
        out = []
        for m in res.scalars().all():
            v = await self.get(m.id)
            if v:
                out.append(v)
        return out
