"""Telegram port — abstract interface used by application and workers.

Infrastructure lives in `infrastructure.telegram.*`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import AsyncIterator, Protocol

from ..domain.value_objects import ContactIdentifier


@dataclass(frozen=True)
class ChannelInfo:
    telegram_id: int
    username: str | None
    title: str
    description: str
    subscribers: int


@dataclass(frozen=True)
class RawMessage:
    channel_id: int
    telegram_message_id: int
    text: str
    posted_at: datetime
    author_user_id: int | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SentMessage:
    telegram_message_id: int
    sent_at: datetime


@dataclass(frozen=True)
class IncomingUpdate:
    """An incoming message from a user we may have contacted."""

    from_user_id: int
    from_chat_id: int
    from_username: str | None
    text: str
    telegram_message_id: int
    posted_at: datetime
    is_reply_to: int | None = None  # telegram message id we sent


class TelegramClientPort(Protocol):
    """Read/write operations for the outreach Telegram account."""

    async def search_channels(self, query: str, limit: int) -> list[ChannelInfo]: ...

    async def get_channel_info(self, telegram_id: int) -> ChannelInfo | None: ...

    async def get_recent_messages(
        self, channel_id: int, limit: int
    ) -> list[RawMessage]: ...

    async def resolve_public_contact(
        self, channel: ChannelInfo
    ) -> tuple[ContactIdentifier, str] | None:
        """Return (identifier, display_name) for the public contact of a channel.

        Returns None when no public contact is available. Implementations MUST
        NOT guess or fabricate owner identity.
        """
        ...

    async def send_message(
        self, recipient: ContactIdentifier, text: str
    ) -> SentMessage: ...

    async def iter_incoming(self) -> AsyncIterator[IncomingUpdate]:
        """Yield incoming updates. The listener owns the long-running task."""
        ...


class TelegramBotPort(Protocol):
    """Separate account: management bot (approval, notifications)."""

    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def notify_pending(self, outreach_id: str, preview: str) -> None: ...
