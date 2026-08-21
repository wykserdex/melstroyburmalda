"""Follow-up worker — runs due follow-ups + schedules new ones for stale ones."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from ..application.use_cases import RunFollowupUseCase, ScheduleFollowupUseCase
from ..config.logging import get_logger
from ..config.settings import Settings
from ..infrastructure.queue.tasks import TaskType
from ..ports.queue import QueuePort, Task
from ..ports.repositories import ConversationRepository
from ..observability.tracing import new_correlation

_log = get_logger(__name__)


class FollowupWorker:
    def __init__(
        self,
        schedule_uc: ScheduleFollowupUseCase,
        run_uc: RunFollowupUseCase,
        queue: QueuePort,
        uow_factory,
        settings: Settings,
        poll_interval_seconds: float = 60.0,
    ) -> None:
        self._schedule = schedule_uc
        self._run = run_uc
        self._queue = queue
        self._uow_factory = uow_factory
        self._settings = settings
        self._interval = poll_interval_seconds
        self._stopped = asyncio.Event()

    async def run(self) -> None:
        _log.info("followup_worker.started", interval=self._interval)
        while not self._stopped.is_set():
            try:
                await self._tick()
            except Exception as e:  # noqa: BLE001
                _log.error("followup_worker.error", error=str(e))
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                pass
        _log.info("followup_worker.stopped")

    async def _tick(self) -> None:
        new_correlation()
        async with self._uow_factory() as uow:
            assert uow.conversations is not None
            now = datetime.utcnow()
            due = await uow.conversations.list_due_followups(now)
        for conv in due:
            await self._run.execute(conv.id)

    async def handle(self, task: Task) -> None:
        new_correlation()
        if task.type == TaskType.SCHEDULE_FOLLOWUP.value:
            await self._schedule.execute(task.payload.get("conversation_id"))
        elif task.type == TaskType.RUN_FOLLOWUP.value:
            await self._run.execute(task.payload.get("conversation_id"))

    def stop(self) -> None:
        self._stopped.set()
