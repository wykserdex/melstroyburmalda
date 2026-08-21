"""N-gram shingle similarity — Jaccard over word 3-grams.

Cheap, deterministic, and easy to test. For embedding-based similarity,
implement a separate adapter behind the same `SimilarityChecker` port.
"""
from __future__ import annotations

import re
from collections.abc import Sequence

from ...ports.similarity import SimilarityChecker, SimilarityResult

_WORD = re.compile(r"[\w]+", re.UNICODE)


def _shingles(text: str, n: int = 3) -> set[str]:
    tokens = _WORD.findall(text.lower())
    if len(tokens) < n:
        return {" ".join(tokens)} if tokens else set()
    return {" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)}


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b) or 1
    return inter / union


class NGramSimilarityChecker(SimilarityChecker):
    def __init__(self, threshold: float = 0.8, n: int = 3) -> None:
        self.threshold = threshold
        self.n = n

    def check(self, candidate: str, history: Sequence[str]) -> SimilarityResult:
        cand_shingles = _shingles(candidate, self.n)
        if not cand_shingles or not history:
            return SimilarityResult(score=0.0, is_too_similar=False)
        best = 0.0
        for prev in history:
            score = jaccard(cand_shingles, _shingles(prev, self.n))
            if score > best:
                best = score
                if best >= self.threshold:
                    return SimilarityResult(score=best, is_too_similar=True)
        return SimilarityResult(score=best, is_too_similar=best >= self.threshold)
