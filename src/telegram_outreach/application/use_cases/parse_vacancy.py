"""parse_vacancy — turn raw message into a Vacancy (or skip)."""
from __future__ import annotations

from ...domain.entities import Contact, Vacancy
from ...domain.entities.contact import Contact as ContactEntity
from ...domain.enums import ContactSource, EventType, VacancyStatus
from ...ports.llm import LLMClientPort
from ...ports.repositories import (
    ContactRepository,
    EventLogRepository,
    MessageRepository,
    VacancyRepository,
)
from .._common import log_event, new_id, now


class ParseVacancyUseCase:
    def __init__(self, llm: LLMClientPort, uow_factory) -> None:
        self._llm = llm
        self._uow_factory = uow_factory

    async def execute(self, message_id: str) -> str | None:
        """Returns the new vacancy id, or None if not a vacancy / duplicate."""
        async with self._uow_factory() as uow:
            assert (
                uow.messages is not None
                and uow.vacancies is not None
                and uow.contacts is not None
                and uow.events is not None
            )
            msg = await uow.messages.get(message_id)
            if msg is None:
                return None

            parse = await self._llm.classify_vacancy(msg.text)
            if not parse.is_vacancy or parse.confidence < 0.4:
                return None

            # dedupe at message level
            existing = await uow.vacancies.get(message_id)  # we keyed on message.id (best effort)
            # We re-fetch via unique message id check
            from ...infrastructure.persistence.models import VacancyModel
            from sqlalchemy import select

            stmt = select(VacancyModel).where(VacancyModel.message_id == msg.id)
            res = await uow.session.execute(stmt)
            if res.scalar_one_or_none() is not None:
                return None

            # Resolve contact (username or author)
            contact = await self._resolve_contact(uow.contacts, msg, parse.contact_username)

            vacancy = Vacancy(
                id=new_id("vac"),
                message=msg,
                kind=parse.kind or "vacancy",
                title=parse.title,
                description=parse.description,
                requirements=parse.requirements,
                contact_hint=contact,
                status=VacancyStatus.PARSED,
                discovered_at=msg.discovered_at,
                parsed_at=now(),
                metadata={
                    "detected_need": parse.title or parse.description[:100],
                    "has_budget": parse.has_budget,
                    "llm_confidence": parse.confidence,
                },
            )
            await uow.vacancies.add(vacancy)
            await uow.vacancies.update_status(vacancy.id, VacancyStatus.PARSED, at=now())
            await log_event(
                uow.events,
                event_type=EventType.VACANCY_PARSED,
                entity_type="vacancy",
                entity_id=vacancy.id,
                metadata={"kind": vacancy.kind, "title": vacancy.title},
            )
            await uow.commit()
            return vacancy.id

    async def _resolve_contact(
        self, contacts: ContactRepository, msg, username_hint: str | None
    ) -> ContactEntity | None:
        candidate_username = (username_hint or "").lstrip("@").lower() or None
        if msg.author_user_id is not None:
            existing = await contacts.get_by_user_id(msg.author_user_id)
            if existing:
                return existing
        if candidate_username:
            existing = await contacts.get_by_username(candidate_username)
            if existing:
                return existing
        if msg.author_user_id or candidate_username:
            ident_kwargs = {}
            if msg.author_user_id:
                ident_kwargs["user_id"] = msg.author_user_id
            if candidate_username:
                ident_kwargs["username"] = candidate_username
            from ...domain.value_objects import ContactIdentifier
            contact = ContactEntity(
                id=new_id("ct"),
                identifier=ContactIdentifier(**ident_kwargs),
                display_name=candidate_username or (str(msg.author_user_id) or "unknown"),
                source=ContactSource.POST_AUTHOR,
            )
            await contacts.add(contact)
            return contact
        return None
