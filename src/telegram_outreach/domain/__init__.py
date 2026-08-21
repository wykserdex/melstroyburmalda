"""Domain layer — pure business rules, no I/O."""
from . import entities, enums, exceptions, policies, scoring
from .value_objects import (
    ContactIdentifier,
    IdempotencyKey,
    MessageBody,
    RelevanceScore,
    TimeWindow,
)

__all__ = [
    "entities",
    "enums",
    "exceptions",
    "policies",
    "scoring",
    "ContactIdentifier",
    "IdempotencyKey",
    "MessageBody",
    "RelevanceScore",
    "TimeWindow",
]
