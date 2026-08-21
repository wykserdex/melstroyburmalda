"""Similarity port — used to detect near-duplicate outbound messages."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class SimilarityResult:
    score: float
    is_too_similar: bool


class SimilarityChecker(Protocol):
    def check(self, candidate: str, history: Sequence[str]) -> SimilarityResult: ...
