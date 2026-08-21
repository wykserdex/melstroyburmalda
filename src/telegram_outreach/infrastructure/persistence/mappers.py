"""Mappers between SQLAlchemy ORM models and domain entities.

The domain stays free of SQLAlchemy; the persistence layer translates.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ...domain.entities import (
    Channel,
    Contact,
    Conversation,
    ConversationMessage,
    EventLogEntry,
    Lead,
    Message,
    Outreach,
    Vacancy,
)
from ...domain.entities.channel import Channel as ChannelEntity
from ...domain.entities.contact import Contact as ContactEntity
from ...domain.entities.conversation import Conversation as ConversationEntity
from ...domain.entities.conversation import ConversationMessage as ConversationMessageEntity
from ...domain.entities.lead import Lead as LeadEntity
from ...domain.entities.message import Message as MessageEntity
from ...domain.entities.outreach import Outreach as OutreachEntity
from ...domain.entities.vacancy import Vacancy as VacancyEntity
from ...domain.enums import (
    ChannelSource,
    ContactSource,
    ConversationStatus,
    EventType,
    LeadStatus,
    OutreachStatus,
    VacancyStatus,
)
from ...domain.value_objects import (
    ContactIdentifier,
    IdempotencyKey,
    MessageBody,
    RelevanceScore,
)
from .models import (
    ChannelModel,
    ContactModel,
    ConversationMessageModel,
    ConversationModel,
    EventLogModel,
    LeadModel,
    MessageModel,
    OutreachModel,
    VacancyModel,
)


# --- Channels & messages -----------------------------------------------------
def channel_to_entity(m: ChannelModel) -> ChannelEntity:
    return ChannelEntity(
        id=m.id,
        telegram_id=m.telegram_id,
        username=m.username,
        title=m.title,
        description=m.description,
        subscribers=m.subscribers,
        source=ChannelSource(m.source),
        discovered_at=m.discovered_at,
        last_scanned_at=m.last_scanned_at,
        metadata=m.meta or {},
        is_active=m.is_active,
    )


def channel_to_model(e: ChannelEntity) -> ChannelModel:
    return ChannelModel(
        id=e.id,
        telegram_id=e.telegram_id,
        username=e.username,
        title=e.title,
        description=e.description,
        subscribers=e.subscribers,
        source=e.source.value,
        discovered_at=e.discovered_at,
        last_scanned_at=e.last_scanned_at,
        is_active=e.is_active,
        meta=e.metadata,
    )


def message_to_entity(m: MessageModel, channel: ChannelEntity) -> MessageEntity:
    return MessageEntity(
        id=m.id,
        channel=channel,
        telegram_message_id=m.telegram_message_id,
        text=m.text,
        posted_at=m.posted_at,
        author_user_id=m.author_user_id,
        metadata=m.meta or {},
        discovered_at=m.discovered_at,
    )


def message_to_model(e: MessageEntity, text_hash: str) -> MessageModel:
    return MessageModel(
        id=e.id,
        channel_id=e.channel.id,
        telegram_message_id=e.telegram_message_id,
        text=e.text,
        text_hash=text_hash,
        posted_at=e.posted_at,
        author_user_id=e.author_user_id,
        meta=e.metadata,
        discovered_at=e.discovered_at,
    )


# --- Vacancies / contacts / leads -------------------------------------------
def vacancy_to_entity(
    m: VacancyModel,
    message: MessageEntity,
    contact_hint: ContactEntity | None = None,
) -> VacancyEntity:
    return VacancyEntity(
        id=m.id,
        message=message,
        kind=m.kind,
        title=m.title,
        description=m.description,
        requirements=list(m.requirements or []),
        contact_hint=contact_hint,
        status=VacancyStatus(m.status),
        discovered_at=m.discovered_at,
        parsed_at=m.parsed_at,
        closed_at=m.closed_at,
        metadata=m.meta or {},
    )


def vacancy_to_model(e: VacancyEntity) -> VacancyModel:
    return VacancyModel(
        id=e.id,
        message_id=e.message.id,
        channel_id=e.message.channel.id,
        kind=e.kind,
        title=e.title,
        description=e.description,
        requirements=e.requirements,
        contact_hint_user_id=e.contact_hint.identifier.user_id if e.contact_hint else None,
        contact_hint_username=e.contact_hint.identifier.username if e.contact_hint else None,
        status=e.status.value,
        discovered_at=e.discovered_at,
        parsed_at=e.parsed_at,
        closed_at=e.closed_at,
        meta=e.metadata,
    )


def contact_to_entity(m: ContactModel) -> ContactEntity:
    return ContactEntity(
        id=m.id,
        identifier=ContactIdentifier(
            user_id=m.user_id,
            username=m.username,
            chat_id=m.chat_id,
        ),
        display_name=m.display_name,
        source=ContactSource(m.source),
        opted_out=m.opted_out,
        opted_out_at=m.opted_out_at,
        created_at=m.created_at,
        metadata=m.meta or {},
    )


def contact_to_model(e: ContactEntity) -> ContactModel:
    return ContactModel(
        id=e.id,
        user_id=e.identifier.user_id,
        username=e.identifier.username,
        chat_id=e.identifier.chat_id,
        display_name=e.display_name,
        source=e.source.value,
        opted_out=e.opted_out,
        opted_out_at=e.opted_out_at,
        created_at=e.created_at,
        meta=e.metadata,
    )


def lead_to_entity(
    m: LeadModel,
    vacancy: VacancyEntity,
    contact: ContactEntity,
) -> LeadEntity:
    return LeadEntity(
        id=m.id,
        vacancy=vacancy,
        contact=contact,
        score=RelevanceScore(value=m.score),
        reason=m.reason,
        scoring_version=m.scoring_version,
        status=LeadStatus(m.status),
        created_at=m.created_at,
        metadata=m.meta or {},
    )


def lead_to_model(e: LeadEntity) -> LeadModel:
    return LeadModel(
        id=e.id,
        vacancy_id=e.vacancy.id,
        contact_id=e.contact.id,
        score=e.score.value,
        reason=e.reason,
        scoring_version=e.scoring_version,
        status=e.status.value,
        created_at=e.created_at,
        meta=e.metadata,
    )


# --- Outreach / conversations -----------------------------------------------
def outreach_to_entity(
    m: OutreachModel,
    lead: LeadEntity,
    contact: ContactEntity,
) -> OutreachEntity:
    return OutreachEntity(
        id=m.id,
        lead=lead,
        contact=contact,
        body=MessageBody(text=m.message_text),
        status=OutreachStatus(m.status),
        prompt_version=m.prompt_version,
        model=m.model,
        generation_metadata=m.generation_meta or {},
        idempotency_key=IdempotencyKey(key=m.idempotency_key) if m.idempotency_key else None,
        created_at=m.created_at,
        approved_at=m.approved_at,
        approved_by=m.approved_by,
        approval_reason=m.approval_reason,
        sent_at=m.sent_at,
        sent_message_id=m.sent_message_id,
        error=m.error,
    )


def outreach_to_model(e: OutreachEntity) -> OutreachModel:
    return OutreachModel(
        id=e.id,
        lead_id=e.lead.id,
        vacancy_id=e.lead.vacancy.id,
        contact_id=e.contact.id,
        message_text=e.body.text,
        status=e.status.value,
        prompt_version=e.prompt_version,
        model=e.model,
        generation_meta=e.generation_metadata,
        idempotency_key=e.idempotency_key.key if e.idempotency_key else "",
        created_at=e.created_at,
        approved_at=e.approved_at,
        approved_by=e.approved_by,
        approval_reason=e.approval_reason,
        sent_at=e.sent_at,
        sent_message_id=e.sent_message_id,
        error=e.error,
    )


def conversation_to_entity(
    m: ConversationModel,
    outreach: OutreachEntity,
    contact: ContactEntity,
) -> ConversationEntity:
    msgs: list[ConversationMessageEntity] = []
    for cm in m.messages:
        msgs.append(
            ConversationMessageEntity(
                direction=cm.direction,
                text=cm.text,
                telegram_message_id=cm.telegram_message_id,
                posted_at=cm.posted_at,
                metadata=cm.meta or {},
            )
        )
    return ConversationEntity(
        id=m.id,
        outreach=outreach,
        contact=contact,
        status=ConversationStatus(m.status),
        messages=msgs,
        last_message_at=m.last_message_at,
        next_followup_at=m.next_followup_at,
        followup_attempts=m.followup_attempts,
        created_at=m.created_at,
        closed_at=m.closed_at,
        metadata=m.meta or {},
    )


def event_to_entity(m: EventLogModel) -> EventLogEntry:
    return EventLogEntry(
        id=m.id,
        event_type=EventType(m.event_type),
        entity_type=m.entity_type,
        entity_id=m.entity_id,
        correlation_id=m.correlation_id,
        created_at=m.created_at,
        metadata=m.meta or {},
    )


def event_to_model(e: EventLogEntry) -> EventLogModel:
    return EventLogModel(
        id=e.id,
        event_type=e.event_type.value,
        entity_type=e.entity_type,
        entity_id=e.entity_id,
        correlation_id=e.correlation_id,
        created_at=e.created_at,
        meta=e.metadata,
    )
