"""Message sender — write side of TelegramClientPort."""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timezone

from telethon.errors import (
    ChatWriteForbiddenError,
    FloodWaitError,
    PeerFloodError,
    UserBannedInChannelError,
    UserIsBlockedError,
)
from telethon.tl.types import PeerChat, PeerUser

from ...config.logging import get_logger
from ...domain.exceptions import (
    DomainError,
    FloodWaitError,
    OptedOut,
    PolicyViolation,
    RateLimited,
)
from ...domain.value_objects import ContactIdentifier
from ...ports.telegram import SentMessage, TelegramClientPort
from .client import TelegramSession

_log = get_logger(__name__)


class TelethonMessageSender:
    """Sends messages with built-in FloodWait handling and basic safety.

    The *worker* (outreach_worker) is responsible for: idempotency check,
    policy check, rate limit. This class is intentionally minimal: it sends
    one message and reports what happened.
    """

    def __init__(self, session: TelegramSession) -> None:
        self._session = session

    async def send_message(
        self, recipient: ContactIdentifier, text: str
    ) -> SentMessage:
        if not recipient.is_resolved():
            raise PolicyViolation("telegram", "recipient has no resolvable id")

        client = self._session.client

        async def _do() -> SentMessage:
            entity = await self._resolve_entity(recipient)
            if entity is None:
                raise PolicyViolation("telegram", f"cannot resolve recipient {recipient}")
            try:
                sent = await client.send_message(entity, text)
            except UserIsBlockedError as e:
                raise OptedOut(f"user blocked us") from e
            except ChatWriteForbiddenError as e:
                raise PolicyViolation("telegram", "chat write forbidden") from e
            except UserBannedInChannelError as e:
                raise PolicyViolation("telegram", "banned in channel") from e
            except PeerFloodError as e:
                raise RateLimited("global", 0.0) from e
            # FloodWaitError is caught in with_flood_wait
            return SentMessage(
                telegram_message_id=sent.id,
                sent_at=datetime.utcnow(),
            )

        return await self._session.with_flood_wait(
            _do,
            on_flood=self._on_flood,
        )

    async def _resolve_entity(self, recipient: ContactIdentifier):
        client = self._session.client
        if recipient.user_id is not None:
            try:
                return await client.get_entity(recipient.user_id)
            except Exception:  # noqa: BLE001
                pass
        if recipient.username:
            try:
                return await client.get_entity(recipient.username)
            except Exception:  # noqa: BLE001
                pass
        if recipient.chat_id is not None:
            try:
                return await client.get_entity(recipient.chat_id)
            except Exception:  # noqa: BLE001
                return None
        return None

    async def _on_flood(self, seconds: int) -> None:
        _log.warning("telegram.flood_wait", seconds=seconds)
        # We honour the wait: this awaits before the call returns.
        await asyncio.sleep(min(seconds, 300) + random.uniform(0, 1))
