"""Policy tests."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from telegram_outreach.domain.enums import OutreachStatus
from telegram_outreach.domain.exceptions import OptedOut, PolicyViolation
from telegram_outreach.domain.policies import (
    DuplicatePolicy,
    FrequencyPolicy,
    MessagePolicy,
    OutreachPolicy,
)
from telegram_outreach.domain.value_objects import MessageBody, RelevanceScore


def test_frequency_can_contact_recipient() -> None:
    p = FrequencyPolicy(
        min_interval_seconds=120,
        per_recipient_cooldown_hours=24,
        daily_message_limit=40,
        global_hourly_limit=20,
    )
    now = datetime(2025, 1, 1, 12, 0, 0)
    ok, why = p.can_contact_recipient(None, now)
    assert ok
    last = now - timedelta(seconds=10)
    ok, why = p.can_contact_recipient(last, now)
    assert not ok
    assert "interval" in (why or "")


def test_message_policy_references_vacancy() -> None:
    p = MessagePolicy(min_mentions_of_need=1, max_length=700)
    body = MessageBody(
        text="Здравствуйте, у меня есть опыт по telegram автоматизации. Готов обсудить детали."
    )
    p.check(body, "Автоматизация входящих заявок Telegram")
    # Now without a keyword match — use shorter body so the requirement triggers
    body2 = MessageBody(text="Короткий текст. Без ключевых слов.")
    with pytest.raises(Exception):  # noqa: BLE001
        p.check(body2, "Автоматизация входящих заявок Telegram")


def test_message_policy_looks_like_template() -> None:
    p = MessagePolicy()
    body = MessageBody(text="Уважаемый клиент. Здравствуйте, я хочу предложить вам услугу.")
    assert p.looks_like_template(body)


def test_outreach_policy_blocks_opted_out() -> None:
    p = OutreachPolicy(
        frequency=FrequencyPolicy(
            min_interval_seconds=0,
            per_recipient_cooldown_hours=0,
            daily_message_limit=10,
            global_hourly_limit=10,
        )
    )

    class FakeContact:
        opted_out = True
        id = "c1"

        def can_be_contacted(self) -> bool:
            return True  # not contactable check passes; opted_out check fails

    with pytest.raises(OptedOut):
        p.can_send(
            outreach=_StubOutreach(),
            contact=FakeContact(),  # type: ignore[arg-type]
            now_sent_today=0,
            now_sent_last_hour=0,
        )


def test_duplicate_policy() -> None:
    p = DuplicatePolicy()
    assert p.is_message_duplicate("c1", 1, {("c1", 1)})
    assert not p.is_message_duplicate("c1", 2, {("c1", 1)})
    assert p.is_text_duplicate("h1", {"h1"})
    assert p.is_outreach_duplicate("k1", {"k1"})


class _StubOutreach:
    body = MessageBody(text="Short body. Two sentences.")
    status = OutreachStatus.APPROVED
    id = "o1"
