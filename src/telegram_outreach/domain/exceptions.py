"""Domain exceptions. Pure, no I/O imports."""
from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain-level errors."""


class InvalidStateTransition(DomainError):
    """Raised when a status machine refuses a transition."""

    def __init__(self, entity: str, current: str, target: str) -> None:
        super().__init__(f"Invalid transition for {entity}: {current} -> {target}")
        self.entity = entity
        self.current = current
        self.target = target


class PolicyViolation(DomainError):
    """Raised when a domain policy refuses an operation."""

    def __init__(self, policy: str, reason: str) -> None:
        super().__init__(f"Policy {policy} violated: {reason}")
        self.policy = policy
        self.reason = reason


class DuplicateEntity(DomainError):
    """Raised when a unique constraint is violated at domain level."""


class MessageValidationError(DomainError):
    """Raised when a draft message fails validation rules."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"Message validation failed: {reason}")
        self.reason = reason


class RateLimited(DomainError):
    """Raised when rate limiter refuses to allow an operation."""

    def __init__(self, scope: str, retry_after: float) -> None:
        super().__init__(f"Rate limited: scope={scope} retry_after={retry_after:.1f}s")
        self.scope = scope
        self.retry_after = retry_after


class FloodWaitError(DomainError):
    """Telegram asked us to wait. We never bypass it."""

    def __init__(self, seconds: int) -> None:
        super().__init__(f"Telegram FloodWait: {seconds}s")
        self.seconds = seconds


class OptedOut(DomainError):
    """Contact has opted out. Do not contact."""


class ConfigurationError(DomainError):
    """Configuration is invalid or missing."""


class LLMContractError(DomainError):
    """LLM returned malformed output we cannot safely use."""
