"""Outreach worker — runs the send_message use case for approved outreaches."""
from __future__ import annotations

from ..application.use_cases import SendMessageUseCase
from ..config.logging import get_logger
from ..config.settings import Settings
from ..infrastructure.queue.tasks import TaskType
from ..ports.queue import QueuePort, Task
from ..ports.repositories import DLQRepository
from ..observability.tracing import new_correlation
from ._base import run_with_retry_and_dlq

_log = get_logger(__name__)


class OutreachWorker:
    def __init__(
        self,
        send: SendMessageUseCase,
        queue: QueuePort,
        uow_factory,
        settings: Settings,
    ) -> None:
        self._send = send
        self._queue = queue
        self._uow_factory = uow_factory
        self._settings = settings

    async def handle(self, task: Task) -> None:
        new_correlation()
        if task.type != TaskType.SEND_OUTREACH.value:
            return
        outreach_id = task.payload.get("outreach_id")
        if not outreach_id:
            return

        async def _op() -> str:
            return await self._send.execute(outreach_id)

        async with self._uow_factory() as uow:
            assert uow.dlq is not None
            await run_with_retry_and_dlq(
                task,
                lambda: _op(),
                uow.dlq,
                self._settings.max_retries,
                self._settings.retry_base_delay,
                self._settings.retry_max_delay,
            )
            await uow.commit()
