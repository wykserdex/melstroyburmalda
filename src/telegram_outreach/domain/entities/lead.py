"""Lead — qualification record tying a Vacancy to a Contact with a score."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..enums import LeadStatus
from ..policies.transitions import assert_lead_transition
from ..value_objects import RelevanceScore
from .contact import Contact
from .vacancy import Vacancy


@dataclass
class Lead:
    """A qualified (or rejected) pairing of vacancy + contact."""

    id: str
    vacancy: Vacancy
    contact: Contact
    score: RelevanceScore
    reason: str
    scoring_version: str
    status: LeadStatus = LeadStatus.QUALIFIED
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def transition(self, target: LeadStatus) -> None:
        assert_lead_transition(self.status, target)
        self.status = target

    def is_qualifiable(self, threshold: float) -> bool:
        return self.score.value >= threshold
