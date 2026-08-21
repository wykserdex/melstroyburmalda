"""Contact entity — the person/chat we may send messages to."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..enums import ContactSource
from ..value_objects import ContactIdentifier


@dataclass
class Contact:
    """Recipient of outreach.

    `opted_out` is sticky: once set True, no new outreach may be created.
    """

    id: str
    identifier: ContactIdentifier
    display_name: str
    source: ContactSource
    opted_out: bool = False
    opted_out_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    def can_be_contacted(self) -> bool:
        return (
            not self.opted_out
            and (self.identifier.user_id is not None or self.identifier.chat_id is not None)
        )

    def opt_out(self, at: datetime | None = None) -> None:
        self.opted_out = True
        self.opted_out_at = at or datetime.utcnow()
