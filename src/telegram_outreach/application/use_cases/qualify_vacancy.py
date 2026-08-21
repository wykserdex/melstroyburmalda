"""qualify_vacancy — combine LLM score with rule-based signals into a Lead."""
from __future__ import annotations

from ...config.settings import Settings
from ...domain.entities import Lead
from ...domain.enums import EventType, LeadStatus, VacancyStatus
from ...ports.llm import LLMClientPort
from ...ports.repositories import (
    ContactRepository,
    EventLogRepository,
    LeadRepository,
    VacancyRepository,
)
from ...domain.scoring import ScoringSignals
from .._common import log_event, new_id


class QualifyVacancyUseCase:
    def __init__(
        self,
        llm: LLMClientPort,
        uow_factory,
        settings: Settings,
    ) -> None:
        self._llm = llm
        self._uow_factory = uow_factory
        self._settings = settings

    async def execute(self, vacancy_id: str) -> str | None:
        """Return the new lead id, or None if rejected / no contact."""
        async with self._uow_factory() as uow:
            assert (
                uow.vacancies is not None
                and uow.leads is not None
                and uow.events is not None
            )
            vac = await uow.vacancies.get(vacancy_id)
            if vac is None:
                return None
            if vac.contact_hint is None:
                await uow.vacancies.update_status(vac.id, VacancyStatus.REJECTED)
                await log_event(
                    uow.events,
                    event_type=EventType.LEAD_REJECTED,
                    entity_type="vacancy",
                    entity_id=vac.id,
                    metadata={"reason": "no contact"},
                )
                await uow.commit()
                return None

            # Already qualified?
            existing = await uow.leads.get_by_vacancy_contact(vac.id, vac.contact_hint.id)
            if existing is not None:
                return existing.id

            score = await self._llm.score_relevance(vac)
            signals = ScoringSignals(
                llm_score=score.score,
                has_contact=bool(vac.contact_hint.identifier.user_id or vac.contact_hint.identifier.username),
                has_requirements=bool(vac.requirements),
                has_budget=bool(vac.metadata.get("has_budget", False)),
                text_length=len(vac.description or ""),
                reason=score.reason,
                scoring_version="v1",
            )
            final = signals.compute()
            reason = signals.reason_text()

            if final.value < self._settings.relevance_threshold:
                await uow.vacancies.update_status(vac.id, VacancyStatus.REJECTED)
                await log_event(
                    uow.events,
                    event_type=EventType.LEAD_REJECTED,
                    entity_type="vacancy",
                    entity_id=vac.id,
                    metadata={"reason": f"score {final.value:.2f} < threshold", "score_reason": reason},
                )
                await uow.commit()
                return None

            lead = Lead(
                id=new_id("lead"),
                vacancy=vac,
                contact=vac.contact_hint,
                score=final,
                reason=reason,
                scoring_version="v1",
                status=LeadStatus.QUALIFIED,
                metadata={"requires_manual_review": final.value < self._settings.confidence_threshold},
            )
            await uow.leads.add(lead)
            await uow.vacancies.update_status(vac.id, VacancyStatus.QUALIFIED)
            await log_event(
                uow.events,
                event_type=EventType.LEAD_QUALIFIED,
                entity_type="lead",
                entity_id=lead.id,
                metadata={"score": final.value, "reason": reason},
            )
            await uow.commit()
            return lead.id
