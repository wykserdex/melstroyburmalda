"""Composite TelegramClientPort that combines scanner, sender, listener.

The application layer talks to this single object. It delegates read calls
to the scanner, write calls to the sender, and the listener pushes to an
asyncio.Queue that workers drain.
"""
from __future__ import annotations

import asyncio
from typing import AsyncIterator

from ...ports.telegram import (
    ChannelInfo,
    IncomingUpdate,
    RawMessage,
    SentMessage,
    TelegramClientPort,
)
from ...domain.value_objects import ContactIdentifier
from .channel_scanner import TelethonChannelScanner
from .message_sender import TelethonMessageSender
from .reply_listener import TelethonReplyListener


class TelegramAdapter(TelegramClientPort):
    """Concrete adapter; the only object application code depends on."""

    def __init__(
        self,
        scanner: TelethonChannelScanner,
        sender: TelethonMessageSender,
        listener: TelethonReplyListener,
        incoming_queue: asyncio.Queue,
    ) -> None:
        self._scanner = scanner
        self._sender = sender
        self._listener = listener
        self._incoming = incoming_queue

    async def search_channels(self, query: str, limit: int) -> list[ChannelInfo]:
        return await self._scanner.search_channels(query, limit)

    async def get_channel_info(self, telegram_id: int) -> ChannelInfo | None:
        return await self._scanner.get_channel_info(telegram_id)

    async def get_recent_messages(self, channel_id: int, limit: int) -> list[RawMessage]:
        return await self._scanner.get_recent_messages(channel_id, limit)

    async def resolve_public_contact(self, channel: ChannelInfo):
        return await self._scanner.resolve_public_contact(channel)

    async def send_message(self, recipient: ContactIdentifier, text: str) -> SentMessage:
        return await self._sender.send_message(recipient, text)

    async def iter_incoming(self) -> AsyncIterator[IncomingUpdate]:
        while True:
            yield await self._incoming.get()
