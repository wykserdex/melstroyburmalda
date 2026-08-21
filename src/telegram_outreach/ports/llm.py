"""LLM port — abstract language model interface."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..domain.entities import Lead, Vacancy


@dataclass(frozen=True)
class VacancyParse:
    is_vacancy: bool
    kind: str
    title: str
    description: str
    requirements: list[str] = field(default_factory=list)
    has_budget: bool = False
    contact_username: str | None = None
    confidence: float = 0.0
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ScoreResult:
    score: float
    reason: str


@dataclass(frozen=True)
class DraftMessage:
    detected_need: str
    proposed_solution: str
    message: str
    raw: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ReplyAnalysis:
    intent: str  # "interested", "not_interested", "question", "opt_out", "other"
    summary: str
    requires_followup: bool = False


class LLMClientPort(Protocol):
    async def classify_vacancy(self, text: str) -> VacancyParse: ...

    async def score_relevance(self, vacancy: Vacancy) -> ScoreResult: ...

    async def generate_message(self, lead: Lead) -> DraftMessage: ...

    async def analyze_reply(
        self, message: str, conversation_context: str
    ) -> ReplyAnalysis: ...
