"""Shared worker helpers — retry policy, DLQ on exhaustion."""
from __future__ import annotations

import asyncio
import random
from typing import Awaitable, Callable, TypeVar

from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config.logging import get_logger
from ..domain.exceptions import (
    ConfigurationError,
    DomainError,
    FloodWaitError,
    OptedOut,
    PolicyViolation,
)
from ..ports.queue import Task
from ..ports.repositories import DLQRepository

_log = get_logger(__name__)
T = TypeVar("T")

# Errors we never retry.
_PERMANENT = (OptedOut, PolicyViolation, ConfigurationError)


def build_retry(max_attempts: int, base_delay: float, max_delay: float):
    def _wait(retry_state: RetryCallState) -> float:
        delay = min(base_delay * (2 ** (retry_state.attempt_number - 1)), max_delay)
        return delay + random.uniform(0, min(1.0, delay * 0.1))

    return AsyncRetrying(
        stop=stop_after_attempt(max_attempts),
        wait=_wait,
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )


async def run_with_retry_and_dlq(
    task: Task,
    op: Callable[[], Awaitable[None]],
    dlq: DLQRepository,
    max_attempts: int,
    base_delay: float,
    max_delay: float,
) -> bool:
    """Run op with retries. On permanent failure or exhaustion, write to DLQ.

    Returns True if op succeeded, False if DLQ'd.
    """
    try:
        async for attempt in build_retry(max_attempts, base_delay, max_delay):
            with attempt:
                await op()
        return True
    except _PERMANENT as e:
        _log.error("worker.permanent_failure", task_id=task.id, error=str(e))
        await dlq.add(task.type, task.payload, f"permanent: {e}", task.attempt + 1)
        return False
    except FloodWaitError as e:
        # We let the queue layer re-schedule with delay; record as event.
        _log.warning("worker.flood_wait", task_id=task.id, seconds=e.seconds)
        raise
    except Exception as e:  # noqa: BLE001
        _log.error("worker.retries_exhausted", task_id=task.id, error=str(e))
        await dlq.add(task.type, task.payload, str(e), task.attempt + 1)
        return False
