"""Repository ports — abstract persistence interfaces.

Each port is small and focused; infrastructure provides SQLAlchemy-backed
implementations.
"""
from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence

from ..domain.entities import (
    Channel,
    Contact,
    Conversation,
    EventLogEntry,
    Lead,
    Message,
    Outreach,
    Vacancy,
)
from ..domain.enums import (
    ConversationStatus,
    EventType,
    IdempotencyState,
    LeadStatus,
    OutreachStatus,
    VacancyStatus,
)
from ..domain.value_objects import IdempotencyKey


# --- Channels & Messages ------------------------------------------------------
class ChannelRepository(Protocol):
    async def get(self, channel_id: str) -> Channel | None: ...
    async def get_by_telegram_id(self, telegram_id: int) -> Channel | None: ...
    async def list_active(self) -> list[Channel]: ...
    async def add(self, channel: Channel) -> None: ...
    async def update_last_scanned(self, channel_id: str, at: datetime) -> None: ...


class MessageRepository(Protocol):
    async def get(self, message_id: str) -> Message | None: ...
    async def get_by_channel_and_tmid(
        self, channel_id: str, telegram_message_id: int
    ) -> Message | None: ...
    async def find_by_text_hash(self, text_hash: str) -> list[Message]: ...
    async def add(self, message: Message) -> None: ...
    async def list_recent_for_channel(
        self, channel_id: str, since: datetime | None
    ) -> list[Message]: ...


# --- Vacancies / Contacts / Leads --------------------------------------------
class VacancyRepository(Protocol):
    async def get(self, vacancy_id: str) -> Vacancy | None: ...
    async def add(self, vacancy: Vacancy) -> None: ...
    async def update_status(
        self, vacancy_id: str, status: VacancyStatus, at: datetime | None = None
    ) -> None: ...
    async def list_by_status(self, status: VacancyStatus) -> list[Vacancy]: ...


class ContactRepository(Protocol):
    async def get(self, contact_id: str) -> Contact | None: ...
    async def get_by_user_id(self, user_id: int) -> Contact | None: ...
    async def get_by_username(self, username: str) -> Contact | None: ...
    async def add(self, contact: Contact) -> None: ...
    async def set_opted_out(self, contact_id: str, at: datetime) -> None: ...
    async def list_opted_out(self) -> list[Contact]: ...


class LeadRepository(Protocol):
    async def get(self, lead_id: str) -> Lead | None: ...
    async def add(self, lead: Lead) -> None: ...
    async def get_by_vacancy_contact(
        self, vacancy_id: str, contact_id: str
    ) -> Lead | None: ...
    async def list_by_status(self, status: LeadStatus) -> list[Lead]: ...
    async def list_for_vacancy(self, vacancy_id: str) -> list[Lead]: ...


# --- Outreach / Conversations ------------------------------------------------
class OutreachRepository(Protocol):
    async def get(self, outreach_id: str) -> Outreach | None: ...
    async def add(self, outreach: Outreach) -> None: ...
    async def update_status(
        self,
        outreach_id: str,
        status: OutreachStatus,
        *,
        sent_message_id: int | None = None,
        approved_by: str | None = None,
        approval_reason: str | None = None,
        at: datetime | None = None,
    ) -> None: ...
    async def list_by_status(self, status: OutreachStatus) -> list[Outreach]: ...
    async def get_by_idempotency_key(self, key: str) -> Outreach | None: ...


class ConversationRepository(Protocol):
    async def get(self, conversation_id: str) -> Conversation | None: ...
    async def get_by_outreach(self, outreach_id: str) -> Conversation | None: ...
    async def add(self, conversation: Conversation) -> None: ...
    async def update_status(
        self,
        conversation_id: str,
        status: ConversationStatus,
        *,
        next_followup_at: datetime | None = None,
        at: datetime | None = None,
    ) -> None: ...
    async def add_message(
        self,
        conversation_id: str,
        direction: str,
        text: str,
        telegram_message_id: int | None,
        posted_at: datetime,
    ) -> None: ...
    async def list_due_followups(self, now: datetime) -> list[Conversation]: ...


# --- Idempotency, DLQ, Events, Rate limits -----------------------------------
class IdempotencyRepository(Protocol):
    async def get(self, key: str) -> tuple[IdempotencyState, str | None] | None: ...
    async def create_pending(
        self, key: IdempotencyKey, entity_type: str, entity_id: str
    ) -> bool:
        """Return True if inserted; False if already existed (and is not terminal)."""
        ...

    async def mark_completed(self, key: str, entity_id: str) -> None: ...
    async def mark_failed(self, key: str) -> None: ...


class DLQRepository(Protocol):
    async def add(
        self,
        job_type: str,
        payload: dict,
        error: str,
        attempts: int,
    ) -> None: ...
    async def list_recent(self, limit: int = 100) -> list[dict]: ...


class EventLogRepository(Protocol):
    async def append(self, entry: EventLogEntry) -> None: ...
    async def list_for_entity(
        self, entity_type: str, entity_id: str
    ) -> list[EventLogEntry]: ...
    async def list_by_type(
        self, event_type: EventType, limit: int = 100
    ) -> list[EventLogEntry]: ...


class RateLimitRepository(Protocol):
    async def count_in_window(
        self, scope: str, window_start: datetime, window_end: datetime
    ) -> int: ...
    async def record(self, scope: str, at: datetime) -> None: ...
    async def last_for_recipient(self, recipient_id: str) -> datetime | None: ...
    async def record_for_recipient(self, recipient_id: str, at: datetime) -> None: ...


# --- Unit of work -------------------------------------------------------------
class UnitOfWork(Protocol):
    """Transactional boundary. Concrete impl uses SQLAlchemy session."""

    async def __aenter__(self) -> "UnitOfWork": ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...


# --- Helpers -----------------------------------------------------------------
def as_seq(items: Sequence | None) -> Sequence:
    return items or []
