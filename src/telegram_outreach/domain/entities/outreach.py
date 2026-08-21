"""Outreach — a single outbound message candidate/result."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..enums import OutreachStatus
from ..policies.transitions import assert_outreach_transition
from ..value_objects import IdempotencyKey, MessageBody
from .contact import Contact
from .lead import Lead


@dataclass
class Outreach:
    """A single outreach attempt for a (lead, contact) pair."""

    id: str
    lead: Lead
    contact: Contact
    body: MessageBody
    status: OutreachStatus = OutreachStatus.DRAFTED
    prompt_version: str = "v1"
    model: str = ""
    generation_metadata: dict[str, Any] = field(default_factory=dict)
    idempotency_key: IdempotencyKey | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    approved_at: datetime | None = None
    approved_by: str | None = None
    approval_reason: str | None = None
    sent_at: datetime | None = None
    sent_message_id: int | None = None
    error: str | None = None

    def transition(self, target: OutreachStatus, at: datetime | None = None) -> None:
        assert_outreach_transition(self.status, target)
        self.status = target
        now = at or datetime.utcnow()
        if target == OutreachStatus.APPROVED:
            self.approved_at = now
        elif target == OutreachStatus.SENT:
            self.sent_at = now

    def approve(self, by: str, reason: str | None = None, at: datetime | None = None) -> None:
        self.transition(OutreachStatus.APPROVED, at=at)
        self.approved_by = by
        self.approval_reason = reason

    def reject(self, reason: str) -> None:
        self.transition(OutreachStatus.REJECTED)
        self.error = reason

    def mark_sent(self, telegram_message_id: int, at: datetime | None = None) -> None:
        self.transition(OutreachStatus.SENT, at=at)
        self.sent_message_id = telegram_message_id

    def mark_failed(self, reason: str) -> None:
        self.transition(OutreachStatus.FAILED)
        self.error = reason
