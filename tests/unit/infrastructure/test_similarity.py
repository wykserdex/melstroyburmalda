"""Similarity / ngram tests."""
from __future__ import annotations

from telegram_outreach.infrastructure.similarity import (
    NGramSimilarityChecker,
    jaccard,
)


def test_jaccard_basic() -> None:
    a = {"a", "b", "c"}
    b = {"b", "c", "d"}
    assert jaccard(a, b) == pytest_approx(0.5)


def pytest_approx(value: float) -> float:  # minimal local helper
    return value


def test_ngram_similarity_too_similar() -> None:
    checker = NGramSimilarityChecker(threshold=0.5)
    msg = "Здравствуйте. У меня есть предложение по автоматизации вашего процесса."
    history = [msg]
    result = checker.check(msg, history)
    assert result.is_too_similar


def test_ngram_similarity_different() -> None:
    checker = NGramSimilarityChecker(threshold=0.9)
    msg = "Здравствуйте, у меня есть идея по ускорению вашего пайплайна."
    history = ["Совсем другой текст. Про другое."]
    result = checker.check(msg, history)
    assert not result.is_too_similar
