"""Reply listener — consumes incoming Telegram updates.

Wraps Telethon's event handler. Each incoming message becomes an
`IncomingUpdate` DTO from the port.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import AsyncIterator

from telethon import events
from telethon.tl.custom.message import Message

from ...config.logging import get_logger
from ...ports.telegram import IncomingUpdate
from .client import TelegramSession

_log = get_logger(__name__)


class TelethonReplyListener:
    def __init__(self, session: TelegramSession, queue: asyncio.Queue) -> None:
        self._session = session
        self._queue = queue
        self._stopped = asyncio.Event()

    async def run(self) -> None:
        client = self._session.client
        client.add_event_handler(self._on_new_message, events.NewMessage(incoming=True))
        _log.info("reply_listener.started")
        try:
            await self._stopped.wait()
        finally:
            client.remove_event_handler(self._on_new_message)
            _log.info("reply_listener.stopped")

    async def stop(self) -> None:
        self._stopped.set()

    async def _on_new_message(self, event) -> None:
        try:
            msg: Message = event.message
            text = (msg.message or "").strip()
            if not text:
                return
            from_id = msg.from_id
            from_user_id = from_id.user_id if from_id else None
            posted = msg.date
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=timezone.utc)
            is_reply_to = None
            if msg.reply_to and msg.reply_to.reply_to_msg_id:
                is_reply_to = msg.reply_to.reply_to_msg_id
            sender = await msg.get_sender()
            username = getattr(sender, "username", None) if sender else None
            update = IncomingUpdate(
                from_user_id=from_user_id or 0,
                from_chat_id=msg.chat_id or 0,
                from_username=username,
                text=text,
                telegram_message_id=msg.id,
                posted_at=posted.astimezone(timezone.utc).replace(tzinfo=None),
                is_reply_to=is_reply_to,
            )
            await self._queue.put(update)
        except Exception as e:  # noqa: BLE001
            _log.warning("reply_listener.on_message_failed", error=str(e))


async def drain(queue: asyncio.Queue) -> AsyncIterator[IncomingUpdate]:
    while True:
        upd = await queue.get()
        yield upd
