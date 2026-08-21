"""Push-уведомление об ожидающем согласования сообщении.

Смысл фичи: до нажатия Approve никому ничего не уходит, поэтому оператор
обязан узнать о черновике сам — карточкой в бот, а не походом в /pending.
"""
from __future__ import annotations

import pytest

from telegram_outreach.bot.notifications import BotNotifier, format_approval_card
from telegram_outreach.domain.entities import (
    Channel,
    Contact,
    Lead,
    Message,
    Outreach,
    Vacancy,
)
from telegram_outreach.domain.enums import ContactSource, OutreachStatus
from telegram_outreach.domain.value_objects import (
    ContactIdentifier,
    MessageBody,
    RelevanceScore,
)
from datetime import datetime


# --- фикстуры ---------------------------------------------------------------

def build_outreach(
    *,
    title: str = "Нужен грузчик на склад",
    channel_title: str = "Работа СПб",
    score: float = 0.42,
    display_name: str = "Иван",
    username: str | None = "ivan_hr",
    text: str = "Здравствуйте! Увидел вашу вакансию. Могу помочь с автоматизацией склада.",
    detected_need: str | None = "автоматизация складского учёта",
) -> Outreach:
    channel = Channel(
        id="ch1",
        telegram_id=1,
        username="rabota_spb",
        title=channel_title,
        description="",
        subscribers=1000,
    )
    message = Message(
        id="msg1",
        channel=channel,
        telegram_message_id=10,
        text=title,
        posted_at=datetime(2026, 8, 21, 12, 0, 0),
    )
    vacancy = Vacancy(id="vac1", message=message, title=title)
    contact = Contact(
        id="c1",
        identifier=ContactIdentifier(user_id=555, username=username),
        display_name=display_name,
        source=ContactSource.POST_AUTHOR,
    )
    lead = Lead(
        id="lead1",
        vacancy=vacancy,
        contact=contact,
        score=RelevanceScore(value=score),
        reason="test",
        scoring_version="v1",
    )
    return Outreach(
        id="out_abc123",
        lead=lead,
        contact=contact,
        body=MessageBody(text=text),
        status=OutreachStatus.DRAFTED,
        generation_metadata={"detected_need": detected_need} if detected_need else {},
    )


class FakeBot:
    """Двойник TelegramBotPort."""

    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple[str, str]] = []
        self._fail = fail

    async def notify_pending(self, outreach_id: str, preview: str) -> None:
        if self._fail:
            raise RuntimeError("telegram недоступен")
        self.calls.append((outreach_id, preview))


# --- карточка ---------------------------------------------------------------

def test_card_contains_everything_needed_for_a_decision():
    card = format_approval_card(build_outreach())

    assert "писать?" in card
    assert "Нужен грузчик на склад" in card          # что нашли
    assert "Работа СПб" in card                       # откуда
    assert "0.42" in card                             # насколько уверены
    assert "Иван" in card and "@ivan_hr" in card      # кому уйдёт
    assert "автоматизацией склада" in card            # что именно отправим
    assert "out_abc123" in card                       # чтобы найти в /pending


def test_card_survives_missing_optional_fields():
    outreach = build_outreach(title="", channel_title="", username=None, detected_need=None)
    card = format_approval_card(outreach)

    assert "без заголовка" in card
    assert "источник неизвестен" in card
    assert "@" not in card.split("Текст")[0].replace("✉️", "")


def test_card_truncates_a_very_long_message():
    # MessageBody ограничен 4096 символами — берём почти предел.
    outreach = build_outreach(text="а" * 4000)
    card = format_approval_card(outreach)

    assert "…" in card
    assert len(card) < 1500, "карточка должна влезать в одно сообщение Telegram"


def test_card_collapses_whitespace_in_title():
    card = format_approval_card(build_outreach(title="Нужен   \n  грузчик"))
    assert "Нужен грузчик" in card


# --- нотификатор ------------------------------------------------------------

async def test_notifier_sends_card_with_outreach_id():
    bot = FakeBot()
    outreach = build_outreach()

    await BotNotifier(bot).pending_outreach(outreach)

    assert len(bot.calls) == 1
    outreach_id, preview = bot.calls[0]
    assert outreach_id == "out_abc123"
    assert "Нужен грузчик на склад" in preview


async def test_notifier_swallows_transport_errors():
    """Недоступность Telegram не должна ронять обработку задачи:
    черновик уже в БД и никуда не денется."""
    bot = FakeBot(fail=True)

    await BotNotifier(bot).pending_outreach(build_outreach())  # не бросает
