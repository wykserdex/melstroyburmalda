"""Conversation — back-and-forth thread around a single Outreach."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..enums import ConversationStatus
from ..policies.transitions import assert_conversation_transition
from .contact import Contact
from .outreach import Outreach


@dataclass
class ConversationMessage:
    """A single message in a conversation thread."""

    direction: str  # "in" or "out"
    text: str
    telegram_message_id: int | None = None
    posted_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Conversation:
    id: str
    outreach: Outreach
    contact: Contact
    status: ConversationStatus = ConversationStatus.OPEN
    messages: list[ConversationMessage] = field(default_factory=list)
    last_message_at: datetime | None = None
    next_followup_at: datetime | None = None
    followup_attempts: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    closed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def transition(self, target: ConversationStatus, at: datetime | None = None) -> None:
        assert_conversation_transition(self.status, target)
        self.status = target
        if target == ConversationStatus.CLOSED:
            self.closed_at = at or datetime.utcnow()

    def add_message(self, msg: ConversationMessage) -> None:
        self.messages.append(msg)
        self.last_message_at = msg.posted_at

    def schedule_followup(self, at: datetime) -> None:
        self.transition(ConversationStatus.FOLLOWUP_SCHEDULED)
        self.next_followup_at = at
        self.followup_attempts += 1

    def cancel_followup(self) -> None:
        self.next_followup_at = None
        if self.status == ConversationStatus.FOLLOWUP_SCHEDULED:
            self.transition(ConversationStatus.WAITING_REPLY)
