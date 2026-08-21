"""send_message — actually send a previously-approved outreach.

Idempotency:
- Pre-check: if an outreach with the same idempotency_key already has
  status SENT, return early.
- Race protection: idempotency_keys row state prevents double-send even
  across restarts.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from ...config.settings import Settings
from ...domain.entities import Conversation
from ...domain.enums import (
    ConversationStatus,
    EventType,
    IdempotencyState,
    LeadStatus,
    OutreachStatus,
)
from ...domain.exceptions import (
    DomainError,
    FloodWaitError,
    OptedOut,
    PolicyViolation,
)
from ...domain.policies import OutreachPolicy
from ...domain.value_objects import IdempotencyKey
from ...ports.queue import QueuePort, Task
from ...ports.repositories import (
    ConversationRepository,
    EventLogRepository,
    IdempotencyRepository,
    OutreachRepository,
    RateLimitRepository,
)
from ...ports.telegram import TelegramClientPort
from ...infrastructure.queue.tasks import TaskType
from .._common import log_event, new_id, now


class SendMessageUseCase:
    def __init__(
        self,
        telegram: TelegramClientPort,
        uow_factory,
        queue: QueuePort,
        settings: Settings,
        outreach_policy: OutreachPolicy,
    ) -> None:
        self._tg = telegram
        self._uow_factory = uow_factory
        self._queue = queue
        self._settings = settings
        self._policy = outreach_policy

    async def execute(self, outreach_id: str) -> str:
        """Returns resulting outreach status."""
        async with self._uow_factory() as uow:
            assert (
                uow.outreach is not None
                and uow.idempotency is not None
                and uow.events is not None
                and uow.conversations is not None
                and uow.rate_limit is not None
            )
            outreach = await uow.outreach.get(outreach_id)
            if outreach is None:
                raise PolicyViolation("send", f"outreach {outreach_id} not found")

            # Idempotency: if already SENT, no-op
            if outreach.status == OutreachStatus.SENT:
                return outreach.status.value

            # Явный гейт согласования. Сейчас задачу на отправку ставит только
            # ApproveMessageUseCase, то есть порядок соблюдается неявно — но
            # одна лишняя постановка задачи (руками, из миграции, из будущего
            # воркера) отправила бы неодобренный черновик живому человеку.
            # Дешевле проверить статус здесь, чем извиняться.
            #
            # Черновик при этом НЕ помечается FAILED: он остаётся в DRAFTED и
            # доступен для согласования через бота — отказ отправить не должен
            # заодно уничтожать кандидата.
            if outreach.status != OutreachStatus.APPROVED:
                await log_event(
                    uow.events,
                    event_type=EventType.MESSAGE_REJECTED,
                    entity_type="outreach",
                    entity_id=outreach.id,
                    metadata={
                        "reason": "send_without_approval",
                        "status": outreach.status.value,
                    },
                )
                await uow.commit()
                raise PolicyViolation(
                    "send",
                    f"outreach {outreach_id} is {outreach.status.value}, expected approved",
                )
            if outreach.idempotency_key is None:
                raise PolicyViolation("send", "missing idempotency key")
            existing = await uow.idempotency.get(outreach.idempotency_key.key)
            if existing is not None and existing[0] == IdempotencyState.COMPLETED:
                # Already sent; reconcile state and exit
                await uow.outreach.update_status(outreach.id, OutreachStatus.SENT)
                await uow.commit()
                return OutreachStatus.SENT.value

            # Pre-flight checks
            if outreach.contact.opted_out:
                await self._mark_failed(uow.events, uow.outreach, outreach.id, "opted_out")
                raise OptedOut("contact opted out")

            # Rate limit: global and per-recipient
            day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            hour_ago = datetime.utcnow() - timedelta(hours=1)
            sent_today = await uow.rate_limit.count_in_window("global", day_start, day_end)
            sent_last_hour = await uow.rate_limit.count_in_window("global", hour_ago, day_end)
            last_for_recipient = await uow.rate_limit.last_for_recipient(outreach.contact.id)
            self._policy.can_send(
                outreach,
                outreach.contact,
                now_sent_today=sent_today,
                now_sent_last_hour=sent_last_hour,
            )
            if last_for_recipient is not None:
                ok, why = self._policy.frequency.can_contact_recipient(
                    last_for_recipient, datetime.utcnow()
                )
                if not ok:
                    raise PolicyViolation("send", why or "cooldown")

            # Idempotency: claim the key (PENDING)
            inserted = await uow.idempotency.create_pending(
                outreach.idempotency_key, "outreach", outreach.id
            )
            if not inserted:
                # Another worker claimed it. Re-check completion.
                row = await uow.idempotency.get(outreach.idempotency_key.key)
                if row and row[0] == IdempotencyState.COMPLETED:
                    await uow.outreach.update_status(outreach.id, OutreachStatus.SENT)
                    await uow.commit()
                    return OutreachStatus.SENT.value
                raise PolicyViolation(
                    "send",
                    f"idempotency key {outreach.idempotency_key.key} already pending",
                )

            await uow.commit()

        # Send outside the UoW (Telegram I/O is slow).
        try:
            sent = await self._tg.send_message(
                outreach.contact.identifier, outreach.body.text
            )
        except FloodWaitError as fw:
            # Re-queue with delay = fw.seconds
            await self._queue.enqueue_delayed(
                Task(
                    id=new_id("task"),
                    type=TaskType.SEND_OUTREACH.value,
                    payload={"outreach_id": outreach_id},
                    max_attempts=self._settings.max_retries,
                ),
                run_at=datetime.utcnow() + timedelta(seconds=fw.seconds),
            )
            async with self._uow_factory() as uow:
                assert uow.events is not None
                await log_event(
                    uow.events,
                    event_type=EventType.FLOOD_WAIT,
                    entity_type="outreach",
                    entity_id=outreach_id,
                    metadata={"seconds": fw.seconds},
                )
                await uow.commit()
            return "flood_wait"
        except OptedOut:
            async with self._uow_factory() as uow:
                await self._mark_failed(uow.events, uow.outreach, outreach_id, "opted_out")
                await uow.commit()
            return OutreachStatus.FAILED.value
        except DomainError as e:
            async with self._uow_factory() as uow:
                await self._mark_failed(uow.events, uow.outreach, outreach_id, str(e))
                await uow.commit()
            return OutreachStatus.FAILED.value

        # Success: mark sent + create conversation
        async with self._uow_factory() as uow:
            assert (
                uow.outreach is not None
                and uow.idempotency is not None
                and uow.conversations is not None
                and uow.rate_limit is not None
                and uow.events is not None
                and uow.leads is not None
            )
            await uow.outreach.update_status(
                outreach_id, OutreachStatus.SENT, sent_message_id=sent.telegram_message_id, at=sent.sent_at
            )
            await uow.idempotency.mark_completed(outreach.idempotency_key.key, outreach_id)
            await uow.rate_limit.record("global", sent.sent_at)
            await uow.rate_limit.record_for_recipient(outreach.contact.id, sent.sent_at)

            # Open a conversation
            conv = Conversation(
                id=new_id("conv"),
                outreach=outreach,
                contact=outreach.contact,
                status=ConversationStatus.WAITING_REPLY,
                last_message_at=sent.sent_at,
            )
            await uow.conversations.add(conv)
            outreach.lead.transition(LeadStatus.OUTREACH_SENT)
            await uow.leads.add(outreach.lead)
            await log_event(
                uow.events,
                event_type=EventType.MESSAGE_SENT,
                entity_type="outreach",
                entity_id=outreach_id,
                metadata={
                    "telegram_message_id": sent.telegram_message_id,
                    "conversation_id": conv.id,
                },
            )
            await uow.commit()
        return OutreachStatus.SENT.value

    @staticmethod
    async def _mark_failed(events, outreach_repo, outreach_id: str, reason: str) -> None:
        await outreach_repo.update_status(outreach_id, OutreachStatus.FAILED)
        await log_event(
            events,
            event_type=EventType.MESSAGE_REJECTED,
            entity_type="outreach",
            entity_id=outreach_id,
            metadata={"reason": reason},
        )
