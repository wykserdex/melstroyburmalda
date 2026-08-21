"""Telethon client factory + lifecycle.

We build a single Telegram client for the outreach account. Management bot
has its own client (see `bot.py`).
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, TypeVar

from telethon import TelegramClient
from telethon.errors import (
    ApiIdInvalidError,
    AuthKeyUnregisteredError,
    FloodWaitError,
    RPCError,
    SessionPasswordNeededError,
)
from telethon.sessions import StringSession

from ...config.settings import Settings
from ...domain.exceptions import FloodWaitError as DomainFloodWaitError

T = TypeVar("T")


class TelegramSession:
    """Thin wrapper around Telethon client with FloodWait handling."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: TelegramClient | None = None

    @property
    def client(self) -> TelegramClient:
        if self._client is None:
            raise RuntimeError("Telegram client not started. Call start() first.")
        return self._client

    async def start(self) -> None:
        if self._client is not None:
            return
        session = (
            StringSession(self._settings.telegram_string_session)
            if self._settings.telegram_string_session
            else self._settings.telegram_session
        )
        self._client = TelegramClient(
            session=session,
            api_id=self._settings.telegram_api_id,
            api_hash=self._settings.telegram_api_hash,
            device_model="telegram-outreach",
            app_version="0.1.0",
            system_version="linux",
            lang_code="en",
            system_lang_code="en",
        )
        await self._client.connect()
        if not await self._client.is_user_authorized():
            # First-time auth: requires interactive phone+code. The bootstrap
            # CLI handles this; for the worker we assume the session already
            # exists. Calling .start() would prompt — we don't do that here.
            raise RuntimeError(
                "Telegram session is not authorised. Run "
                "`python -m telegram_outreach.auth` to log in."
            )

    async def stop(self) -> None:
        if self._client is None:
            return
        try:
            await self._client.disconnect()
        finally:
            self._client = None

    async def with_flood_wait(
        self,
        op: Callable[[], Awaitable[T]],
        *,
        on_flood: Callable[[int], Awaitable[None]] | None = None,
    ) -> T:
        """Invoke op, translating Telethon FloodWaitError into a domain error.

        The caller decides what to do — wait, requeue, or DLQ. We never
        silently swallow FloodWait.
        """
        try:
            return await op()
        except FloodWaitError as e:
            seconds = int(e.seconds)
            if on_flood is not None:
                await on_flood(seconds)
            raise DomainFloodWaitError(seconds=seconds) from e

    async def __aenter__(self) -> "TelegramSession":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.stop()
