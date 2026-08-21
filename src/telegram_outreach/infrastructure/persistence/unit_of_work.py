"""SQLAlchemy-backed Unit of Work.

Wraps a session and exposes repositories. Use as:
    async with uow_factory() as uow:
        await uow.channels.add(...)
        await uow.commit()
"""
from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .repositories import (
    SqlChannelRepository,
    SqlContactRepository,
    SqlConversationRepository,
    SqlDLQRepository,
    SqlEventLogRepository,
    SqlIdempotencyRepository,
    SqlLeadRepository,
    SqlMessageRepository,
    SqlOutreachRepository,
    SqlRateLimitRepository,
    SqlVacancyRepository,
)


class SqlUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self.session: AsyncSession | None = None
        self.channels: SqlChannelRepository | None = None
        self.messages: SqlMessageRepository | None = None
        self.vacancies: SqlVacancyRepository | None = None
        self.contacts: SqlContactRepository | None = None
        self.leads: SqlLeadRepository | None = None
        self.outreach: SqlOutreachRepository | None = None
        self.conversations: SqlConversationRepository | None = None
        self.idempotency: SqlIdempotencyRepository | None = None
        self.dlq: SqlDLQRepository | None = None
        self.events: SqlEventLogRepository | None = None
        self.rate_limit: SqlRateLimitRepository | None = None

    async def __aenter__(self) -> Self:
        self.session = self._session_factory()
        self.channels = SqlChannelRepository(self.session)
        self.messages = SqlMessageRepository(self.session)
        self.vacancies = SqlVacancyRepository(self.session)
        self.contacts = SqlContactRepository(self.session)
        self.leads = SqlLeadRepository(self.session)
        self.outreach = SqlOutreachRepository(self.session)
        self.conversations = SqlConversationRepository(self.session)
        self.idempotency = SqlIdempotencyRepository(self.session)
        self.dlq = SqlDLQRepository(self.session)
        self.events = SqlEventLogRepository(self.session)
        self.rate_limit = SqlRateLimitRepository(self.session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self.session is None:
            return
        try:
            if exc is not None:
                await self.session.rollback()
            else:
                await self.session.commit()
        finally:
            await self.session.close()
            self.session = None

    async def commit(self) -> None:
        if self.session is not None:
            await self.session.commit()

    async def rollback(self) -> None:
        if self.session is not None:
            await self.session.rollback()
