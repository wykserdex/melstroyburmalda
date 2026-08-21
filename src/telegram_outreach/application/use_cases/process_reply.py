"""process_reply — handle an incoming Telegram message.

Steps:
1. Identify the conversation by sent_message_id (reply_to).
2. Append the message to the conversation.
3. Classify the reply via LLM.
4. If opt_out → set contact.opted_out, cancel follow-ups, close conversation.
5. If not_interested → close conversation.
6. If interested/question → mark REPLIED, optionally schedule follow-up.
"""
from __future__ import annotations

from ...config.settings import Settings
from ...domain.enums import (
    ConversationStatus,
    EventType,
    OutreachStatus,
)
from ...domain.exceptions import DomainError
from ...ports.llm import LLMClientPort
from ...ports.queue import QueuePort, Task
from ...ports.repositories import (
    ContactRepository,
    ConversationRepository,
    EventLogRepository,
    OutreachRepository,
)
from ...infrastructure.queue.tasks import TaskType
from .._common import log_event, new_id, now


class ProcessReplyUseCase:
    def __init__(
        self,
        llm: LLMClientPort,
        uow_factory,
        queue: QueuePort,
        settings: Settings,
    ) -> None:
        self._llm = llm
        self._uow_factory = uow_factory
        self._queue = queue
        self._settings = settings

    async def execute(
        self,
        *,
        from_user_id: int,
        from_chat_id: int,
        from_username: str | None,
        text: str,
        telegram_message_id: int,
        posted_at,
        is_reply_to: int | None,
    ) -> str | None:
        async with self._uow_factory() as uow:
            assert (
                uow.outreach is not None
                and uow.conversations is not None
                and uow.contacts is not None
                and uow.events is not None
            )

            # Find the conversation by the message we sent (reply_to)
            conversation = None
            if is_reply_to is not None:
                from sqlalchemy import select
                from ...infrastructure.persistence.models import OutreachModel

                stmt = select(OutreachModel).where(
                    OutreachModel.sent_message_id == is_reply_to
                )
                res = await uow.session.execute(stmt)
                row = res.scalar_one_or_none()
                if row is not None:
                    conversation = await uow.conversations.get_by_outreach(row.id)

            if conversation is None:
                # We got a reply from a user we never contacted. Ignore.
                return None

            # Add inbound message
            await uow.conversations.add_message(
                conversation.id,
                direction="in",
                text=text,
                telegram_message_id=telegram_message_id,
                posted_at=posted_at,
            )

            # Classify
            try:
                analysis = await self._llm.analyze_reply(
                    text,
                    conversation_context=conversation.outreach.body.text,
                )
            except DomainError:
                analysis = None

            if analysis is not None and analysis.intent == "opt_out":
                await uow.contacts.set_opted_out(conversation.contact.id, now())
                await uow.conversations.update_status(
                    conversation.id, ConversationStatus.CLOSED, at=now()
                )
                await uow.outreach.update_status(
                    conversation.outreach.id, OutreachStatus.CLOSED
                )
                await log_event(
                    uow.events,
                    event_type=EventType.OPT_OUT,
                    entity_type="contact",
                    entity_id=conversation.contact.id,
                )
                await log_event(
                    uow.events,
                    event_type=EventType.REPLY_RECEIVED,
                    entity_type="conversation",
                    entity_id=conversation.id,
                    metadata={"intent": "opt_out"},
                )
                await uow.commit()
                return "opted_out"

            if analysis is not None and analysis.intent == "not_interested":
                await uow.conversations.update_status(
                    conversation.id, ConversationStatus.CLOSED, at=now()
                )
                await uow.outreach.update_status(
                    conversation.outreach.id, OutreachStatus.CLOSED
                )
                await log_event(
                    uow.events,
                    event_type=EventType.REPLY_RECEIVED,
                    entity_type="conversation",
                    entity_id=conversation.id,
                    metadata={"intent": "not_interested"},
                )
                await uow.commit()
                return "closed"

            # Interested / question / other: keep conversation open
            await uow.conversations.update_status(
                conversation.id, ConversationStatus.REPLIED, at=now()
            )
            await uow.outreach.update_status(
                conversation.outreach.id, OutreachStatus.REPLIED
            )
            await log_event(
                uow.events,
                event_type=EventType.REPLY_ANALYZED,
                entity_type="conversation",
                entity_id=conversation.id,
                metadata={"intent": (analysis.intent if analysis else "other")},
            )
            await uow.commit()
            return analysis.intent if analysis else "received"
