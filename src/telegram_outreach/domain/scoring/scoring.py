"""Scoring / qualification — heuristic rules in front of an LLM score.

LLM gives a `score` and `reason`; this module combines them with rule-based
signals (e.g. explicit budget, contact present, requirements listed) to
produce a final `RelevanceScore`.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..value_objects import RelevanceScore


@dataclass(frozen=True)
class ScoringSignals:
    llm_score: float
    has_contact: bool
    has_requirements: bool
    has_budget: bool
    text_length: int
    reason: str = ""
    scoring_version: str = "v1"

    def compute(self) -> RelevanceScore:
        score = self.llm_score
        # Slight bonus for well-formed vacancies; never invent info.
        if self.has_requirements:
            score += 0.03
        if self.has_contact:
            score += 0.04
        if self.has_budget:
            score += 0.03
        if self.text_length < 40:
            score -= 0.05
        score = max(0.0, min(1.0, score))
        return RelevanceScore(value=round(score, 3))

    def reason_text(self) -> str:
        parts: list[str] = []
        if self.reason:
            parts.append(self.reason)
        flags = []
        if self.has_requirements:
            flags.append("requirements_listed")
        if self.has_contact:
            flags.append("contact_present")
        if self.has_budget:
            flags.append("budget_mentioned")
        if flags:
            parts.append("signals=" + ",".join(flags))
        return "; ".join(parts) or "no signals"


def is_manual_review(score: RelevanceScore, threshold: float, confidence: float) -> bool:
    """Below confidence threshold we require a human to approve."""
    return score.value < confidence
