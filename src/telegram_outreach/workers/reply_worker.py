"""Reply worker — drains incoming Telegram updates."""
from __future__ import annotations

import asyncio

from ..application.use_cases import ProcessReplyUseCase
from ..config.logging import get_logger
from ..observability.tracing import new_correlation
from ..ports.telegram import IncomingUpdate as TelegramIncomingUpdate

_log = get_logger(__name__)


class ReplyWorker:
    def __init__(self, process_reply: ProcessReplyUseCase, incoming: asyncio.Queue) -> None:
        self._process = process_reply
        self._incoming = incoming
        self._stopped = asyncio.Event()

    async def run(self) -> None:
        _log.info("reply_worker.started")
        while not self._stopped.is_set():
            try:
                upd: TelegramIncomingUpdate = await asyncio.wait_for(
                    self._incoming.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue
            try:
                new_correlation()
                result = await self._process.execute(
                    from_user_id=upd.from_user_id,
                    from_chat_id=upd.from_chat_id,
                    from_username=upd.from_username,
                    text=upd.text,
                    telegram_message_id=upd.telegram_message_id,
                    posted_at=upd.posted_at,
                    is_reply_to=upd.is_reply_to,
                )
                _log.info("reply_worker.processed", result=result)
            except Exception as e:  # noqa: BLE001
                _log.error("reply_worker.error", error=str(e))
        _log.info("reply_worker.stopped")

    def stop(self) -> None:
        self._stopped.set()
