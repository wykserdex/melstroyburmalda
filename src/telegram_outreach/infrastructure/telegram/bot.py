"""Telethon-адаптер управляющего бота (TelegramBotPort).

Порт `notify_pending` был объявлен, но не реализован ни одним классом —
поэтому уведомления об ожидающих согласования сообщениях физически не
могли никуда уйти. Это его реализация.

Бот работает на отдельном аккаунте (bot_token) и никогда не пишет
получателям: он общается только с операторами из BOT_ALLOWED_USERS.
"""
from __future__ import annotations

from ...config.logging import get_logger

_log = get_logger(__name__)


class TelethonBotNotifier:
    """Рассылает карточки согласования операторам бота."""

    def __init__(self, client, allowed_user_ids: list[int]) -> None:
        self._client = client
        self._allowed_user_ids = list(allowed_user_ids)

    async def start(self) -> None:  # pragma: no cover - управляется main.py
        """Жизненным циклом клиента владеет main.py (start/disconnect)."""

    async def stop(self) -> None:  # pragma: no cover - управляется main.py
        """См. start()."""

    async def notify_pending(self, outreach_id: str, preview: str) -> None:
        if not self._allowed_user_ids:
            _log.warning("bot.notify_skipped", reason="no_allowed_users")
            return

        # Импорт внутри функции: клавиатуры тянут telethon.tl.custom, а модуль
        # инфраструктуры импортируется и там, где бот отключён.
        from ...bot.keyboards import approval_keyboard

        buttons = approval_keyboard(outreach_id)

        delivered = 0
        for user_id in self._allowed_user_ids:
            try:
                await self._client.send_message(user_id, preview, buttons=buttons)
                delivered += 1
            except Exception as e:  # noqa: BLE001
                # Недоступность одного оператора не должна ронять уведомление
                # остальным: тот, кто на связи, всё равно увидит карточку.
                _log.warning(
                    "bot.notify_user_failed",
                    outreach_id=outreach_id,
                    user_id=user_id,
                    error=str(e),
                )

        _log.info(
            "bot.notify_pending",
            outreach_id=outreach_id,
            delivered=delivered,
            recipients=len(self._allowed_user_ids),
        )
