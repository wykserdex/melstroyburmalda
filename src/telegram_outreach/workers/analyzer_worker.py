"""Analyzer worker — for each new message: parse → dedupe → qualify.

The queue holds `parse_vacancy` and `qualify_vacancy` task types. We
consume them and run the appropriate use case.
"""
from __future__ import annotations

import asyncio

from ..application.use_cases import (
    DeduplicateUseCase,
    GenerateMessageUseCase,
    ParseVacancyUseCase,
    QualifyVacancyUseCase,
)
from ..config.logging import get_logger
from ..config.settings import Settings
from ..infrastructure.queue.tasks import TaskType
from ..ports.queue import QueuePort, Task
from ..ports.repositories import VacancyRepository
from ..observability.tracing import new_correlation
from ._base import run_with_retry_and_dlq

_log = get_logger(__name__)


class AnalyzerWorker:
    def __init__(
        self,
        parse: ParseVacancyUseCase,
        dedupe: DeduplicateUseCase,
        qualify: QualifyVacancyUseCase,
        generate: GenerateMessageUseCase,
        queue: QueuePort,
        uow_factory,
        settings: Settings,
    ) -> None:
        self._parse = parse
        self._dedupe = dedupe
        self._qualify = qualify
        self._generate = generate
        self._queue = queue
        self._uow_factory = uow_factory
        self._settings = settings

    async def handle(self, task: Task) -> None:
        new_correlation()
        if task.type == TaskType.PARSE_VACANCY.value:
            await self._handle_parse(task)
        elif task.type == TaskType.QUALIFY_VACANCY.value:
            await self._handle_qualify(task)
        else:
            _log.warning("analyzer_worker.unknown_task", task_type=task.type)

    async def _handle_parse(self, task: Task) -> None:
        message_id = task.payload.get("message_id")
        if not message_id:
            return

        async def _op() -> None:
            vac_id = await self._parse.execute(message_id)
            if vac_id is None:
                return
            # Then dedupe and qualify
            deduped = await self._dedupe.execute(vac_id)
            if not deduped:
                lead_id = await self._qualify.execute(vac_id)
                if lead_id is not None:
                    # Generate (and possibly auto-approve below)
                    outreach_id = await self._generate.execute(lead_id)
                    if outreach_id is not None:
                        if self._settings.auto_approve and (
                            await self._is_high_confidence(lead_id)
                        ):
                            from ..application.use_cases import ApproveMessageUseCase

                            approver = ApproveMessageUseCase(
                                self._uow_factory, self._queue, self._settings
                            )
                            await approver.execute(
                                outreach_id, approved_by="auto", reason="auto_approve", auto=True
                            )

        async with self._uow_factory() as uow:
            assert uow.dlq is not None
            ok = await run_with_retry_and_dlq(
                task,
                _op,
                uow.dlq,
                self._settings.max_retries,
                self._settings.retry_base_delay,
                self._settings.retry_max_delay,
            )
            if ok:
                await uow.commit()

    async def _handle_qualify(self, task: Task) -> None:
        vacancy_id = task.payload.get("vacancy_id")
        if not vacancy_id:
            return
        lead_id = await self._qualify.execute(vacancy_id)
        if lead_id is not None:
            await self._generate.execute(lead_id)

    async def _is_high_confidence(self, lead_id: str) -> bool:
        async with self._uow_factory() as uow:
            lead = await uow.leads.get(lead_id)
            if lead is None:
                return False
            return lead.score.value >= self._settings.confidence_threshold
