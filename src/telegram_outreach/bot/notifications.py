"""Notification helpers for the management bot."""
from __future__ import annotations

from ..config.logging import get_logger
from ..ports.telegram import TelegramBotPort  # type: ignore[attr-defined]

_log = get_logger(__name__)


class BotNotifier:
    def __init__(self, bot: TelegramBotPort) -> None:
        self._bot = bot

    async def pending(self, outreach_id: str, preview: str) -> None:
        try:
            await self._bot.notify_pending(outreach_id, preview)
        except Exception as e:  # noqa: BLE001
            _log.warning("bot.notify_failed", error=str(e))
