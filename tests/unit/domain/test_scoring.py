"""Scoring tests."""
from __future__ import annotations

from telegram_outreach.domain.scoring import ScoringSignals, is_manual_review


def test_scoring_combines_signals() -> None:
    s = ScoringSignals(
        llm_score=0.7,
        has_contact=True,
        has_requirements=True,
        has_budget=True,
        text_length=200,
        reason="backend integration",
    )
    final = s.compute()
    # 0.7 + 0.03 + 0.04 + 0.03 = 0.80
    assert 0.78 <= float(final) <= 0.82
    assert "backend integration" in s.reason_text()
    assert "requirements_listed" in s.reason_text()


def test_scoring_low_text_penalty() -> None:
    s = ScoringSignals(
        llm_score=0.5,
        has_contact=False,
        has_requirements=False,
        has_budget=False,
        text_length=10,
    )
    final = s.compute()
    assert float(final) < 0.5


def test_scoring_manual_review_threshold() -> None:
    from telegram_outreach.domain.value_objects import RelevanceScore

    assert is_manual_review(RelevanceScore(value=0.5), threshold=0.6, confidence=0.75)
    assert not is_manual_review(RelevanceScore(value=0.8), threshold=0.6, confidence=0.75)
