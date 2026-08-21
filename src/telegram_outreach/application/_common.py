"""Shared helpers for use cases.

Use cases are short and focused; this module holds the bits that would
otherwise be copy-pasted: event logging, id generation, idempotency.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from ..config.logging import get_logger
from ..domain.entities import EventLogEntry
from ..domain.enums import EventType
from ..observability.tracing import current_correlation_id

_log = get_logger(__name__)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


async def log_event(
    events_repo,
    *,
    event_type: EventType,
    entity_type: str,
    entity_id: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    cid = current_correlation_id()
    entry = EventLogEntry(
        id=new_id("evt"),
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        correlation_id=cid,
        metadata=metadata or {},
    )
    try:
        await events_repo.append(entry)
    except Exception as e:  # noqa: BLE001
        # Event log must never break business flow.
        _log.warning("event.append_failed", event_type=event_type.value, error=str(e))


def now() -> datetime:
    return datetime.utcnow()
