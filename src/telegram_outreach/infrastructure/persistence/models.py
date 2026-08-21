"""SQLAlchemy 2.x ORM models. These are persistence-only.

Domain code must NOT import from this module. Mappers in `mappers.py`
translate between these and the domain entities.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

JSONType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


# --- Channels & messages ------------------------------------------------------
class ChannelModel(Base):
    __tablename__ = "channels"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    subscribers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="search", nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_scanned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    messages: Mapped[list["MessageModel"]] = relationship(
        back_populates="channel", lazy="selectin"
    )


class MessageModel(Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("channel_id", "telegram_message_id", name="uq_msg_chan_tmid"),
        Index("ix_msg_text_hash", "text_hash"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    channel_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    author_user_id: Mapped[int | None] = mapped_column(BigInteger)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    channel: Mapped[ChannelModel] = relationship(back_populates="messages")


# --- Vacancies / contacts / leads --------------------------------------------
class VacancyModel(Base):
    __tablename__ = "vacancies"
    __table_args__ = (
        UniqueConstraint("message_id", name="uq_vacancy_message"),
        Index("ix_vacancy_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    message_id: Mapped[str] = mapped_column(String(64), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="vacancy", nullable=False)
    title: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    requirements: Mapped[list[str]] = mapped_column(JSONType, default=list, nullable=False)
    contact_hint_user_id: Mapped[int | None] = mapped_column(BigInteger)
    contact_hint_username: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)


class ContactModel(Base):
    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    username: Mapped[str | None] = mapped_column(String(64), index=True)
    chat_id: Mapped[int | None] = mapped_column(BigInteger)
    display_name: Mapped[str] = mapped_column(String(256), default="", nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    opted_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    meta: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)


class LeadModel(Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("vacancy_id", "contact_id", name="uq_lead_vacancy_contact"),
        Index("ix_lead_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    vacancy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    contact_id: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(Text, default="", nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(16), default="v1", nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    meta: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)


# --- Outreach / conversations ------------------------------------------------
class OutreachModel(Base):
    __tablename__ = "outreach"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_outreach_idem"),
        Index("ix_outreach_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lead_id: Mapped[str] = mapped_column(String(64), nullable=False)
    vacancy_id: Mapped[str] = mapped_column(String(64), nullable=False)
    contact_id: Mapped[str] = mapped_column(String(64), nullable=False)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    generation_meta: Mapped[dict[str, Any]] = mapped_column(
        JSONType, default=dict, nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_by: Mapped[str | None] = mapped_column(String(64))
    approval_reason: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_message_id: Mapped[int | None] = mapped_column(BigInteger)
    error: Mapped[str | None] = mapped_column(Text)


class ConversationModel(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conv_status", "status"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    outreach_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    contact_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_followup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    followup_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    messages: Mapped[list["ConversationMessageModel"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class ConversationMessageModel(Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (Index("ix_cmsg_conv", "conversation_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # in/out
    text: Mapped[str] = mapped_column(Text, nullable=False)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)

    conversation: Mapped[ConversationModel] = relationship(back_populates="messages")


# --- Idempotency / DLQ / events / rate-limits -------------------------------
class IdempotencyModel(Base):
    __tablename__ = "idempotency_keys"

    key: Mapped[str] = mapped_column(String(160), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DLQModel(Base):
    __tablename__ = "dlq"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)
    error: Mapped[str] = mapped_column(Text, default="", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EventLogModel(Base):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_event_entity", "entity_type", "entity_id"),
        Index("ix_event_type", "event_type"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    meta: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict, nullable=False)


class RateLimitBucketModel(Base):
    """Persistent counter for daily/hourly/per-recipient rate limit checks."""

    __tablename__ = "rate_limit_buckets"
    __table_args__ = (Index("ix_rl_scope_time", "scope", "ts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    recipient_id: Mapped[str | None] = mapped_column(String(64))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
