"""Channel entity — content source (Telegram channel in MVP)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..enums import ChannelSource


@dataclass
class Channel:
    """A source of messages we monitor.

    `telegram_id` is the canonical identifier for Telegram sources.
    `username` is optional (private channels may have none).
    """

    id: str
    telegram_id: int
    username: str | None
    title: str
    description: str
    subscribers: int
    source: ChannelSource = ChannelSource.SEARCH
    discovered_at: datetime = field(default_factory=datetime.utcnow)
    last_scanned_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True

    def mark_scanned(self, at: datetime) -> None:
        self.last_scanned_at = at

    def matches_excluded(self, excluded_channels: list[str], excluded_keywords: list[str]) -> bool:
        if self.username and self.username.lower() in excluded_channels:
            return True
        title_lc = self.title.lower()
        return any(kw in title_lc for kw in excluded_keywords)

    def meets_min_subscribers(self, minimum: int) -> bool:
        return self.subscribers >= minimum
