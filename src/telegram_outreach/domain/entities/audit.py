"""Audit / event log entry — append-only."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..enums import EventType


@dataclass
class EventLogEntry:
    id: str
    event_type: EventType
    entity_type: str
    entity_id: str
    correlation_id: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)
