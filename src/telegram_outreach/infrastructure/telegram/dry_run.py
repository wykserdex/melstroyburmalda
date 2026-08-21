"""Dry-run wrapper around TelegramClientPort.

When `--dry-run` is set, this adapter is used in place of the real one. It
permits all read operations but blocks any write — `send_message` raises a
clear error rather than performing the call.
"""
from __future__ import annotations

from typing import AsyncIterator

from ...config.logging import get_logger
from ...domain.exceptions import PolicyViolation
from ...domain.value_objects import ContactIdentifier
from ...ports.telegram import (
    ChannelInfo,
    IncomingUpdate,
    RawMessage,
    SentMessage,
    TelegramClientPort,
)

_log = get_logger(__name__)


class DryRunTelegramClient(TelegramClientPort):
    def __init__(self, real: TelegramClientPort) -> None:
        self._real = real

    async def search_channels(self, query: str, limit: int) -> list[ChannelInfo]:
        return await self._real.search_channels(query, limit)

    async def get_channel_info(self, telegram_id: int) -> ChannelInfo | None:
        return await self._real.get_channel_info(telegram_id)

    async def get_recent_messages(self, channel_id: int, limit: int) -> list[RawMessage]:
        return await self._real.get_recent_messages(channel_id, limit)

    async def resolve_public_contact(self, channel: ChannelInfo):
        return await self._real.resolve_public_contact(channel)

    async def send_message(self, recipient: ContactIdentifier, text: str) -> SentMessage:
        _log.warning("dry_run.blocked_send", recipient=str(recipient), length=len(text))
        raise PolicyViolation(
            "dry_run",
            "send_message is not allowed in dry-run mode",
        )

    async def iter_incoming(self) -> AsyncIterator[IncomingUpdate]:
        # No updates during dry-run
        if False:
            yield
