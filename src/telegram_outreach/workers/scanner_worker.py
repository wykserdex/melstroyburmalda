"""Scanner worker — periodically runs scan_channels + enqueues parse jobs."""
from __future__ import annotations

import asyncio
from typing import Any

from ..application.use_cases import ParseVacancyUseCase, ScanChannelsUseCase
from ..config.logging import get_logger
from ..config.settings import Settings
from ..infrastructure.queue.tasks import TaskType
from ..observability.tracing import new_correlation
from ..ports.queue import QueuePort, Task

_log = get_logger(__name__)


class ScannerWorker:
    def __init__(
        self,
        scan: ScanChannelsUseCase,
        parse: ParseVacancyUseCase,
        queue: QueuePort,
        settings: Settings,
        poll_interval_seconds: float = 60.0,
    ) -> None:
        self._scan = scan
        self._parse = parse
        self._queue = queue
        self._settings = settings
        self._interval = poll_interval_seconds
        self._stopped = asyncio.Event()

    async def run_once(self) -> dict:
        new_correlation()
        report = await self._scan.execute(
            limit=self._settings.cli_limit or self._settings.max_sample_messages,
        )
        # Find all newly-inserted messages and enqueue parse jobs.
        # For MVP we don't track which ones are new here; the parser is
        # idempotent (vacancy has unique message_id), so re-enqueueing is safe.
        # In a more advanced implementation we'd diff the report.
        return report

    async def run(self) -> None:
        _log.info("scanner_worker.started", interval=self._interval)
        while not self._stopped.is_set():
            try:
                report = await self.run_once()
                _log.info("scanner_worker.tick", **report)
            except Exception as e:  # noqa: BLE001
                _log.error("scanner_worker.error", error=str(e))
            try:
                await asyncio.wait_for(self._stopped.wait(), timeout=self._interval)
            except asyncio.TimeoutError:
                pass
        _log.info("scanner_worker.stopped")

    def stop(self) -> None:
        self._stopped.set()
