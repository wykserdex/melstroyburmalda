"""Raw message entity — what came in from a Channel, before parsing."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .channel import Channel


@dataclass
class Message:
    """A single raw message from a Channel.

    Not all messages become Vacancies — most are filtered by the parser.
    """

    id: str
    channel: Channel
    telegram_message_id: int
    text: str
    posted_at: datetime
    author_user_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    discovered_at: datetime = field(default_factory=datetime.utcnow)

    def text_hash(self) -> str:
        import hashlib
        normalised = " ".join(self.text.lower().split())
        return hashlib.sha256(normalised.encode("utf-8")).hexdigest()
