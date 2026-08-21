"""schedule_followup + run_followup — manage the follow-up lifecycle.

`schedule_followup` is a *decision*: it does not send anything, it just
creates a delayed task. `run_followup` is the actual send, re-checking
all preconditions (opt-out, new reply, conversation status, rate limits).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from ...config.settings import Settings
from ...domain.enums import (
    ConversationStatus,
    EventType,
    OutreachStatus,
)
from ...domain.exceptions import PolicyViolation
from ...ports.queue import QueuePort, Task
from ...ports.repositories import (
    ConversationRepository,
    EventLogRepository,
    OutreachRepository,
)
from ...ports.telegram import TelegramClientPort
from ...infrastructure.queue.tasks import TaskType
from .._common import log_event, new_id, now


class ScheduleFollowupUseCase:
    def __init__(
        self,
        uow_factory,
        queue: QueuePort,
        settings: Settings,
    ) -> None:
        self._uow_factory = uow_factory
        self._queue = queue
        self._settings = settings

    async def execute(self, conversation_id: str) -> str | None:
        async with self._uow_factory() as uow:
            assert uow.conversations is not None and uow.events is not None
            conv = await uow.conversations.get(conversation_id)
            if conv is None:
                return None
            if conv.contact.opted_out:
                return None
            if conv.status in {
                ConversationStatus.CLOSED,
                ConversationStatus.FOLLOWUP_SCHEDULED,
                ConversationStatus.REPLIED,
            }:
                return None
            if conv.followup_attempts >= self._settings.max_followups:
                return None

            run_at = now() + timedelta(hours=self._settings.followup_delay_hours)
            await uow.conversations.update_status(
                conv.id, ConversationStatus.FOLLOWUP_SCHEDULED, next_followup_at=run_at
            )
            await log_event(
                uow.events,
                event_type=EventType.FOLLOWUP_SCHEDULED,
                entity_type="conversation",
                entity_id=conv.id,
                metadata={"run_at": run_at.isoformat(), "attempt": conv.followup_attempts + 1},
            )
            await uow.commit()

        await self._queue.enqueue_delayed(
            Task(
                id=new_id("task"),
                type=TaskType.RUN_FOLLOWUP.value,
                payload={"conversation_id": conversation_id},
                max_attempts=self._settings.max_retries,
            ),
            run_at=run_at,
        )
        return run_at.isoformat()


class RunFollowupUseCase:
    def __init__(
        self,
        telegram: TelegramClientPort,
        uow_factory,
        settings: Settings,
    ) -> None:
        self._tg = telegram
        self._uow_factory = uow_factory
        self._settings = settings

    async def execute(self, conversation_id: str) -> str:
        async with self._uow_factory() as uow:
            assert (
                uow.conversations is not None
                and uow.outreach is not None
                and uow.events is not None
            )
            conv = await uow.conversations.get(conversation_id)
            if conv is None:
                return "missing"
            if conv.contact.opted_out:
                return "opted_out"
            if conv.status in {ConversationStatus.CLOSED}:
                return "closed"
            if conv.status == ConversationStatus.REPLIED:
                # Replied after scheduling — cancel.
                await uow.conversations.update_status(
                    conv.id, ConversationStatus.WAITING_REPLY
                )
                await log_event(
                    uow.events,
                    event_type=EventType.FOLLOWUP_CANCELLED,
                    entity_type="conversation",
                    entity_id=conv.id,
                    metadata={"reason": "user_replied"},
                )
                await uow.commit()
                return "cancelled_replied"

            # For MVP, follow-up is a no-op send. The message is derived from
            # the original outreach body + a soft reminder suffix. Future
            # iterations may generate a fresh follow-up copy.
            followup_text = (
                conv.outreach.body.text.rstrip(".")
                + "\n\nЕсли актуально — дайте знать, я готов уточнить детали."
            )
            try:
                sent = await self._tg.send_message(
                    conv.contact.identifier, followup_text
                )
            except Exception as e:  # noqa: BLE001
                await log_event(
                    uow.events,
                    event_type=EventType.MESSAGE_REJECTED,
                    entity_type="conversation",
                    entity_id=conv.id,
                    metadata={"reason": f"followup_send_failed: {e}"},
                )
                await uow.commit()
                return "failed"

            await uow.conversations.add_message(
                conv.id,
                direction="out",
                text=followup_text,
                telegram_message_id=sent.telegram_message_id,
                posted_at=sent.sent_at,
            )
            await uow.conversations.update_status(
                conv.id,
                ConversationStatus.WAITING_REPLY,
                next_followup_at=None,
            )
            await uow.outreach.update_status(
                conv.outreach.id, OutreachStatus.SENT
            )
            await log_event(
                uow.events,
                event_type=EventType.MESSAGE_SENT,
                entity_type="outreach",
                entity_id=conv.outreach.id,
                metadata={"kind": "followup", "telegram_message_id": sent.telegram_message_id},
            )
            await uow.commit()
            return "sent"
