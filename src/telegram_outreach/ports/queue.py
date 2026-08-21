"""Queue port — abstract async task queue."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Awaitable, Callable, Protocol


@dataclass
class Task:
    """A unit of work scheduled for async processing."""

    id: str
    type: str
    payload: dict = field(default_factory=dict)
    run_at: datetime | None = None
    correlation_id: str | None = None
    attempt: int = 0
    max_attempts: int = 5

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "payload": self.payload,
            "run_at": self.run_at.isoformat() if self.run_at else None,
            "correlation_id": self.correlation_id,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        run_at = d.get("run_at")
        return cls(
            id=d["id"],
            type=d["type"],
            payload=d.get("payload", {}),
            run_at=datetime.fromisoformat(run_at) if run_at else None,
            correlation_id=d.get("correlation_id"),
            attempt=d.get("attempt", 0),
            max_attempts=d.get("max_attempts", 5),
        )


TaskHandler = Callable[[Task], Awaitable[None]]


class QueuePort(Protocol):
    async def enqueue(self, task: Task) -> None: ...
    async def enqueue_delayed(self, task: Task, run_at: datetime) -> None: ...
    async def consume(self, handler: TaskHandler) -> None: ...
    async def acknowledge(self, task_id: str) -> None: ...
    async def reject(self, task_id: str, requeue: bool) -> None: ...
    async def size(self) -> int: ...
