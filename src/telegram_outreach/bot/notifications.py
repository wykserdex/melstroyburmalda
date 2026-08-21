"""Notification helpers for the management bot.

Это push-половина approval-воркфлоу. Pull-половина (`/pending`) была здесь
с самого начала, но она требует, чтобы оператор сам вспомнил и спросил —
а до тех пор черновик молча лежит в БД. Уведомление закрывает ровно этот
разрыв: как только пайплайн подготовил сообщение, карточка сама приезжает
в бот с кнопками Approve/Reject.
"""
from __future__ import annotations

from ..config.logging import get_logger
from ..domain.entities import Outreach
from ..ports.telegram import TelegramBotPort  # type: ignore[attr-defined]

_log = get_logger(__name__)

_PREVIEW_LIMIT = 700
_TITLE_LIMIT = 120
_SOURCE_LIMIT = 60


def _trim(value: str, limit: int) -> str:
    value = " ".join((value or "").split())
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def format_approval_card(outreach: Outreach) -> str:
    """Собирает карточку «нашёл X — писать?».

    Оператор должен принять решение, не выходя из чата, поэтому в карточке
    есть всё для отказа: что за вакансия, откуда она, насколько уверен
    скоринг, кому именно уйдёт сообщение и его полный текст.
    """
    lead = outreach.lead
    vacancy = lead.vacancy
    contact = outreach.contact

    title = _trim(vacancy.title, _TITLE_LIMIT) or "без заголовка"

    channel = getattr(getattr(vacancy.message, "channel", None), "title", "") or ""
    source = _trim(channel, _SOURCE_LIMIT) or "источник неизвестен"

    recipient = contact.display_name or ""
    username = getattr(contact.identifier, "username", None)
    if username:
        recipient = f"{recipient} (@{username})".strip()
    recipient = _trim(recipient, _SOURCE_LIMIT) or "получатель не определён"

    need = outreach.generation_metadata.get("detected_need") or ""

    lines = [
        "🔎 *Нашёл вакансию — писать?*",
        "",
        f"*{title}*",
        f"📡 {source}",
        f"🎯 Скоринг: {lead.score.value:.2f}",
        f"👤 Получатель: {recipient}",
    ]
    if need:
        lines.append(f"💡 Потребность: {_trim(need, 160)}")
    lines += [
        "",
        "✉️ *Текст, который уйдёт:*",
        _trim(outreach.body.text, _PREVIEW_LIMIT),
        "",
        f"`{outreach.id}`",
    ]
    return "\n".join(lines)


class BotNotifier:
    def __init__(self, bot: TelegramBotPort) -> None:
        self._bot = bot

    async def pending(self, outreach_id: str, preview: str) -> None:
        try:
            await self._bot.notify_pending(outreach_id, preview)
        except Exception as e:  # noqa: BLE001
            _log.warning("bot.notify_failed", error=str(e))

    async def pending_outreach(self, outreach: Outreach) -> None:
        """Уведомить оператора о черновике, ждущем решения."""
        await self.pending(outreach.id, format_approval_card(outreach))
