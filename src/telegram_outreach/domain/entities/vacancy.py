"""Vacancy entity — a parsed lead of type 'vacancy' (or any future kind)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..enums import VacancyStatus
from ..policies.transitions import assert_vacancy_transition
from .contact import Contact
from .message import Message


@dataclass
class Vacancy:
    """Parsed lead.

    `kind` allows extension to orders, service requests, etc. without
    refactoring the model.
    """

    id: str
    message: Message
    kind: str = "vacancy"
    title: str = ""
    description: str = ""
    requirements: list[str] = field(default_factory=list)
    contact_hint: Contact | None = None
    status: VacancyStatus = VacancyStatus.DISCOVERED
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    parsed_at: datetime | None = None
    closed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def transition(self, target: VacancyStatus, at: datetime | None = None) -> None:
        assert_vacancy_transition(self.status, target)
        self.status = target
        now = at or datetime.utcnow()
        if target == VacancyStatus.PARSED:
            self.parsed_at = now
        elif target == VacancyStatus.CLOSED:
            self.closed_at = now

    def is_active(self) -> bool:
        return self.status not in {VacancyStatus.DUPLICATE, VacancyStatus.CLOSED, VacancyStatus.REJECTED}
