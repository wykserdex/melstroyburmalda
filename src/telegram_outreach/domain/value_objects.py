"""Value objects — small, immutable, validated.

Pydantic is used for validation only; these objects do not perform I/O.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator

from .exceptions import MessageValidationError


class RelevanceScore(BaseModel):
    """0..1 score with a small tolerance for floating point comparison."""

    value: float = Field(..., ge=0.0, le=1.0)

    def __float__(self) -> float:
        return self.value

    def __lt__(self, other: "RelevanceScore") -> bool:
        return self.value < other.value

    def __ge__(self, other: "RelevanceScore") -> bool:
        return self.value >= other.value


class MessageBody(BaseModel):
    """Validated text body. Centralises length and quality rules."""

    text: str = Field(..., min_length=1, max_length=4096)
    min_sentences: int = 2
    max_sentences: int = 5
    forbidden_phrases: tuple[str, ...] = (
        "купите", "скидка", "акция", "бесплатно",
        "гарантирую", "лучший", "дешёво", "заработок",
        "миллион", "пассивный доход",
    )

    @field_validator("text")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def sentence_count(self) -> int:
        # Sentence boundary heuristic — good enough for MVP validation.
        parts = re.split(r"[.!?]+(?:\s|$)", self.text.strip())
        return len([p for p in parts if p.strip()])

    def sentences(self) -> list[str]:
        return [s.strip() for s in re.split(r"(?<=[.!?])\s+", self.text) if s.strip()]

    def contains_forbidden(self) -> list[str]:
        lowered = self.text.lower()
        return [p for p in self.forbidden_phrases if p in lowered]

    def validate(self) -> None:
        if not self.text:
            raise MessageValidationError("empty text")
        n = self.sentence_count
        if n < self.min_sentences or n > self.max_sentences:
            raise MessageValidationError(
                f"sentence count {n} not in [{self.min_sentences},{self.max_sentences}]"
            )
        bad = self.contains_forbidden()
        if bad:
            raise MessageValidationError(f"forbidden phrases: {bad}")


class IdempotencyKey(BaseModel):
    """Deterministic key to prevent duplicate side-effects."""

    key: str = Field(..., min_length=8, max_length=128)

    @classmethod
    def build(
        cls,
        operation: str,
        parts: list[Any],
        version: str = "v1",
    ) -> "IdempotencyKey":
        h = hashlib.sha256()
        h.update(version.encode("utf-8"))
        h.update(b"|")
        h.update(operation.encode("utf-8"))
        h.update(b"|")
        for p in parts:
            h.update(str(p).encode("utf-8"))
            h.update(b"|")
        return cls(key=f"{operation}:{h.hexdigest()[:32]}")


class TimeWindow(BaseModel):
    """Inclusive time interval, used by rate limiter and follow-ups."""

    start: float  # epoch seconds
    end: float

    @field_validator("end")
    @classmethod
    def _check(cls, v: float, info: Any) -> float:
        start = info.data.get("start")
        if start is not None and v < start:
            raise ValueError("end before start")
        return v

    def contains(self, ts: float) -> bool:
        return self.start <= ts <= self.end


class ContactIdentifier(BaseModel):
    """Telegram identifier for a contact. At least one of user_id/username."""

    user_id: int | None = None
    username: str | None = None
    chat_id: int | None = None

    @field_validator("username")
    @classmethod
    def _normalise(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().lstrip("@").lower()
        return v or None

    def is_resolved(self) -> bool:
        return self.user_id is not None or self.chat_id is not None
