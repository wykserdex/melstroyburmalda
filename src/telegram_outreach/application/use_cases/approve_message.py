"""approve_message / reject_message — human action on a drafted outreach.

In AUTO_APPROVE mode (and high-confidence leads), approval is automatic.
"""
from __future__ import annotations

from ...config.settings import Settings
from ...domain.entities import Outreach
from ...domain.enums import EventType, LeadStatus, OutreachStatus
from ...ports.queue import QueuePort
from ...ports.repositories import (
    EventLogRepository,
    LeadRepository,
    OutreachRepository,
)
from ...infrastructure.queue.tasks import TaskType
from ...ports.queue import Task
from .._common import log_event, new_id, now


class ApproveMessageUseCase:
    def __init__(self, uow_factory, queue: QueuePort, settings: Settings) -> None:
        self._uow_factory = uow_factory
        self._queue = queue
        self._settings = settings

    async def execute(
        self,
        outreach_id: str,
        *,
        approved_by: str = "human",
        reason: str | None = None,
        auto: bool = False,
    ) -> bool:
        async with self._uow_factory() as uow:
            assert (
                uow.outreach is not None
                and uow.events is not None
                and uow.leads is not None
            )
            outreach = await uow.outreach.get(outreach_id)
            if outreach is None:
                return False
            if outreach.status != OutreachStatus.DRAFTED:
                return False

            outreach.approve(approved_by, reason, at=now())
            await uow.outreach.update_status(
                outreach.id,
                OutreachStatus.APPROVED,
                approved_by=approved_by,
                approval_reason=reason,
                at=now(),
            )
            outreach.lead.transition(LeadStatus.OUTREACH_APPROVED)
            await uow.leads.add(outreach.lead)
            await log_event(
                uow.events,
                event_type=EventType.MESSAGE_APPROVED,
                entity_type="outreach",
                entity_id=outreach.id,
                metadata={"by": approved_by, "auto": auto, "reason": reason},
            )
            await uow.commit()

        # Enqueue the send job
        await self._queue.enqueue(
            Task(
                id=new_id("task"),
                type=TaskType.SEND_OUTREACH.value,
                payload={"outreach_id": outreach_id},
                max_attempts=self._settings.max_retries,
            )
        )
        return True


class RejectMessageUseCase:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, outreach_id: str, *, reason: str) -> bool:
        async with self._uow_factory() as uow:
            assert uow.outreach is not None and uow.events is not None
            outreach = await uow.outreach.get(outreach_id)
            if outreach is None:
                return False
            outreach.reject(reason=reason)
            await uow.outreach.update_status(outreach.id, OutreachStatus.REJECTED)
            await log_event(
                uow.events,
                event_type=EventType.MESSAGE_REJECTED,
                entity_type="outreach",
                entity_id=outreach.id,
                metadata={"reason": reason},
            )
            await uow.commit()
            return True
