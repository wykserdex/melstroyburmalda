"""Message policy — additional quality checks beyond MessageBody.validate.

These rules are domain-level (e.g. personalised, references the vacancy).
The actual *similarity* check against history is delegated to a port and
applied at the application layer.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..exceptions import MessageValidationError
from ..value_objects import MessageBody


@dataclass(frozen=True)
class MessagePolicy:
    min_mentions_of_need: int = 1
    max_length: int = 700

    def check(self, body: MessageBody, vacancy_title: str) -> None:
        body.validate()
        if len(body.text) > self.max_length:
            raise MessageValidationError(f"text too long: {len(body.text)}")
        # At least one piece of the vacancy should be referenced (loosely).
        keywords = [w.lower() for w in re.findall(r"\w{4,}", vacancy_title) if len(w) >= 4]
        body_lc = body.text.lower()
        hits = sum(1 for kw in keywords if kw in body_lc)
        if keywords and hits < self.min_mentions_of_need:
            # Soft check: if title is empty, skip.
            if vacancy_title.strip():
                raise MessageValidationError(
                    f"message does not reference the vacancy (need >= {self.min_mentions_of_need})"
                )

    def looks_like_template(self, body: MessageBody) -> bool:
        """Detect obvious templated / generic text."""
        generic_markers = (
            "уважаемый клиент",
            "здравствуйте, я хочу предложить",
            "доброго времени суток",
            "коммерческое предложение",
        )
        lowered = body.text.lower()
        return any(m in lowered for m in generic_markers)
