"""High-level LLM message generator. Builds a `DraftMessage` and validates
it before returning it to the application layer.
"""
from __future__ import annotations

from ...domain.entities import Lead
from ...domain.exceptions import LLMContractError, MessageValidationError
from ...domain.value_objects import MessageBody
from ...ports.llm import LLMClientPort


class LLMMessageGenerator:
    def __init__(self, llm: LLMClientPort) -> None:
        self._llm = llm

    async def generate(self, lead: Lead) -> tuple[MessageBody, str, str]:
        """Return (validated body, detected_need, proposed_solution).

        Raises MessageValidationError if the body is unfit (caller decides).
        """
        draft = await self._llm.generate_message(lead)
        if not draft.message:
            raise LLMContractError("LLM returned empty message")
        body = MessageBody(text=draft.message)
        body.validate()
        return body, draft.detected_need, draft.proposed_solution
