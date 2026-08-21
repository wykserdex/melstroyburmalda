"""DTOs are simple data containers used to pass data into use cases.

They are intentionally separate from domain entities so that callers (CLI,
bot) don't reach into rich behaviour.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class ChannelDTO:
    telegram_id: int
    username: str | None
    title: str
    description: str
    subscribers: int


@dataclass(frozen=True)
class MessageDTO:
    channel_telegram_id: int
    telegram_message_id: int
    text: str
    posted_at: datetime
    author_user_id: int | None = None


@dataclass(frozen=True)
class VacancyDTO:
    title: str
    description: str
    requirements: list[str]
    has_budget: bool
    contact_username: str | None
    confidence: float
    kind: str = "vacancy"


@dataclass(frozen=True)
class LeadDTO:
    score: float
    reason: str


@dataclass(frozen=True)
class DraftMessageDTO:
    detected_need: str
    proposed_solution: str
    message: str
    body_valid: bool
    similarity_too_high: bool
    reference_vacancy_id: str


@dataclass(frozen=True)
class SendResultDTO:
    outreach_id: str
    status: str
    sent_at: datetime | None
    error: str | None = None
    telegram_message_id: int | None = None


@dataclass(frozen=True)
class ReplyDTO:
    telegram_message_id: int
    text: str
    posted_at: datetime
    from_user_id: int | None = None
    from_username: str | None = None
    is_reply_to: int | None = None
    extra: dict[str, Any] | None = None
