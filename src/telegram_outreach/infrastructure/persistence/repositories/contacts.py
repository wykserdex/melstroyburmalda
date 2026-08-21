"""Contact repository."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.entities import Contact
from ..mappers import contact_to_entity, contact_to_model
from ..models import ContactModel


class SqlContactRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, contact_id: str) -> Contact | None:
        m = await self.session.get(ContactModel, contact_id)
        return contact_to_entity(m) if m else None

    async def get_by_user_id(self, user_id: int) -> Contact | None:
        stmt = select(ContactModel).where(ContactModel.user_id == user_id)
        res = await self.session.execute(stmt)
        m = res.scalar_one_or_none()
        return contact_to_entity(m) if m else None

    async def get_by_username(self, username: str) -> Contact | None:
        stmt = select(ContactModel).where(ContactModel.username == username.lower().lstrip("@"))
        res = await self.session.execute(stmt)
        m = res.scalar_one_or_none()
        return contact_to_entity(m) if m else None

    async def add(self, contact: Contact) -> None:
        existing = await self.session.get(ContactModel, contact.id)
        if existing is not None:
            return
        self.session.add(contact_to_model(contact))

    async def set_opted_out(self, contact_id: str, at: datetime) -> None:
        stmt = (
            update(ContactModel)
            .where(ContactModel.id == contact_id)
            .values(opted_out=True, opted_out_at=at)
        )
        await self.session.execute(stmt)

    async def list_opted_out(self) -> list[Contact]:
        stmt = select(ContactModel).where(ContactModel.opted_out.is_(True))
        res = await self.session.execute(stmt)
        return [contact_to_entity(m) for m in res.scalars().all()]
