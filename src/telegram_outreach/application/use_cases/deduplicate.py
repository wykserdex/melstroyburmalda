"""deduplicate — mark a vacancy as DUPLICATE if its message or text was seen.

Triggered by the analyzer worker after parse. We look at all messages
across channels that share the same text hash.
"""
from __future__ import annotations

from ...domain.enums import EventType, VacancyStatus
from ...ports.repositories import (
    EventLogRepository,
    MessageRepository,
    VacancyRepository,
)
from .._common import log_event, now


class DeduplicateUseCase:
    def __init__(self, uow_factory) -> None:
        self._uow_factory = uow_factory

    async def execute(self, vacancy_id: str) -> bool:
        """Return True if the vacancy was deduplicated."""
        async with self._uow_factory() as uow:
            assert (
                uow.vacancies is not None
                and uow.messages is not None
                and uow.events is not None
            )
            vac = await uow.vacancies.get(vacancy_id)
            if vac is None:
                return False
            msg = vac.message
            text_hash = msg.text_hash()
            # Already seen? (any message with the same text hash and earlier discovery)
            others = await uow.messages.find_by_text_hash(text_hash)
            seen = [m for m in others if m.id != msg.id and m.discovered_at < msg.discovered_at]
            if not seen:
                return False
            # Mark as duplicate
            await uow.vacancies.update_status(vac.id, VacancyStatus.DUPLICATE, at=now())
            await log_event(
                uow.events,
                event_type=EventType.VACANCY_DEDUPLICATED,
                entity_type="vacancy",
                entity_id=vac.id,
                metadata={"matches": [m.id for m in seen[:5]]},
            )
            await uow.commit()
            return True
