"""generate_message — produce a draft Outreach from a Lead.

Includes:
- similarity check against recent history
- message policy validation
- idempotency key construction
- status transition to DRAFTED
"""
from __future__ import annotations

from ...config.settings import Settings
from ...domain.entities import Outreach
from ...domain.enums import EventType, LeadStatus, OutreachStatus
from ...domain.exceptions import MessageValidationError, OptedOut, PolicyViolation
from ...domain.policies import MessagePolicy, OutreachPolicy
from ...domain.value_objects import IdempotencyKey
from ...infrastructure.llm.message_generator import LLMMessageGenerator
from ...ports.llm import LLMClientPort
from ...ports.repositories import (
    EventLogRepository,
    LeadRepository,
    OutreachRepository,
)
from ...ports.similarity import SimilarityChecker
from .._common import log_event, new_id


class GenerateMessageUseCase:
    def __init__(
        self,
        llm: LLMClientPort,
        message_generator: LLMMessageGenerator,
        similarity: SimilarityChecker,
        message_policy: MessagePolicy,
        outreach_policy: OutreachPolicy,
        uow_factory,
        settings: Settings,
    ) -> None:
        self._llm = llm
        self._generator = message_generator
        self._similarity = similarity
        self._message_policy = message_policy
        self._outreach_policy = outreach_policy
        self._uow_factory = uow_factory
        self._settings = settings

    async def execute(self, lead_id: str) -> str | None:
        """Return outreach id on success; None if blocked."""
        async with self._uow_factory() as uow:
            assert (
                uow.leads is not None
                and uow.outreach is not None
                and uow.events is not None
            )
            lead = await uow.leads.get(lead_id)
            if lead is None:
                return None
            contact = lead.contact

            if contact.opted_out:
                await log_event(
                    uow.events,
                    event_type=EventType.LEAD_REJECTED,
                    entity_type="lead",
                    entity_id=lead.id,
                    metadata={"reason": "opted_out"},
                )
                return None

            try:
                body, detected_need, proposed_solution = await self._generator.generate(lead)
            except MessageValidationError as e:
                await log_event(
                    uow.events,
                    event_type=EventType.MESSAGE_REJECTED,
                    entity_type="lead",
                    entity_id=lead.id,
                    metadata={"reason": str(e)},
                )
                return None

            try:
                self._message_policy.check(body, lead.vacancy.title)
            except MessageValidationError as e:
                await log_event(
                    uow.events,
                    event_type=EventType.MESSAGE_REJECTED,
                    entity_type="lead",
                    entity_id=lead.id,
                    metadata={"reason": str(e)},
                )
                return None

            # Similarity check against recent history
            recent = await uow.outreach.list_by_status(OutreachStatus.SENT)
            recent_texts = [o.body.text for o in recent[-50:]]
            sim = self._similarity.check(body.text, recent_texts)
            if sim.is_too_similar:
                await log_event(
                    uow.events,
                    event_type=EventType.MESSAGE_REJECTED,
                    entity_type="lead",
                    entity_id=lead.id,
                    metadata={"reason": "too_similar", "score": sim.score},
                )
                return None

            idem = IdempotencyKey.build(
                "outreach",
                [lead.vacancy.id, contact.id, "v1"],
                version=self._settings.prompt_version,
            )

            # Idempotency: if an outreach with the same key already exists, reuse it.
            existing = await uow.outreach.get_by_idempotency_key(idem.key)
            if existing is not None:
                return existing.id

            outreach = Outreach(
                id=new_id("out"),
                lead=lead,
                contact=contact,
                body=body,
                status=OutreachStatus.DRAFTED,
                prompt_version=self._settings.prompt_version,
                model=self._settings.ollama_model,
                generation_metadata={
                    "detected_need": detected_need,
                    "proposed_solution": proposed_solution,
                    "similarity_score": sim.score,
                    "requires_approval": lead.score.value < self._settings.confidence_threshold,
                },
                idempotency_key=idem,
            )
            try:
                self._outreach_policy.can_generate(lead, contact, body)
            except (OptedOut, PolicyViolation) as e:
                outreach.reject(reason=str(e))
            await uow.outreach.add(outreach)
            lead.transition(LeadStatus.OUTREACH_DRAFTED)
            # Persist the lead status by re-adding (idempotent).
            await uow.leads.add(lead)
            await log_event(
                uow.events,
                event_type=EventType.MESSAGE_DRAFTED,
                entity_type="outreach",
                entity_id=outreach.id,
                metadata={
                    "lead_id": lead.id,
                    "vacancy_id": lead.vacancy.id,
                    "score": lead.score.value,
                },
            )
            await uow.commit()
            return outreach.id
