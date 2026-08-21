"""Entity behaviour tests."""
from __future__ import annotations

from datetime import datetime

import pytest

from telegram_outreach.domain.entities import (
    Channel,
    Contact,
    Lead,
    Outreach,
    Vacancy,
)
from telegram_outreach.domain.entities.message import Message
from telegram_outreach.domain.enums import (
    ChannelSource,
    ContactSource,
    LeadStatus,
    OutreachStatus,
    VacancyStatus,
)
from telegram_outreach.domain.exceptions import InvalidStateTransition
from telegram_outreach.domain.value_objects import (
    ContactIdentifier,
    IdempotencyKey,
    MessageBody,
    RelevanceScore,
)


def _channel() -> Channel:
    return Channel(
        id="ch1",
        telegram_id=100,
        username="foo",
        title="Foo",
        description="",
        subscribers=500,
    )


def test_channel_min_subs() -> None:
    ch = _channel()
    assert ch.meets_min_subscribers(100)
    assert not ch.meets_min_subscribers(1000)


def test_channel_excluded() -> None:
    ch = _channel()
    assert ch.matches_excluded(["foo"], [])
    assert ch.matches_excluded([], ["foo"])  # title doesn't have it though
    ch2 = Channel(
        id="c", telegram_id=1, username=None, title="Spam Bar", description="", subscribers=10
    )
    assert ch2.matches_excluded([], ["spam"])


def test_vacancy_transition() -> None:
    ch = _channel()
    msg = Message(
        id="m1",
        channel=ch,
        telegram_message_id=1,
        text="Need Python developer",
        posted_at=datetime.utcnow(),
    )
    v = Vacancy(id="v1", message=msg)
    v.transition(VacancyStatus.PARSED)
    v.transition(VacancyStatus.QUALIFIED)
    with pytest.raises(InvalidStateTransition):
        v.transition(VacancyStatus.DISCOVERED)


def test_contact_can_be_contacted() -> None:
    c = Contact(
        id="c1",
        identifier=ContactIdentifier(user_id=1),
        display_name="X",
        source=ContactSource.POST_AUTHOR,
    )
    assert c.can_be_contacted()
    c.opt_out()
    assert not c.can_be_contacted()


def test_outreach_approve_and_send() -> None:
    ch = _channel()
    msg = Message(
        id="m1", channel=ch, telegram_message_id=1, text="x", posted_at=datetime.utcnow()
    )
    contact = Contact(
        id="c1",
        identifier=ContactIdentifier(user_id=1),
        display_name="x",
        source=ContactSource.POST_AUTHOR,
    )
    v = Vacancy(id="v1", message=msg)
    lead = Lead(
        id="l1",
        vacancy=v,
        contact=contact,
        score=RelevanceScore(value=0.9),
        reason="r",
        scoring_version="v1",
    )
    o = Outreach(
        id="o1",
        lead=lead,
        contact=contact,
        body=MessageBody(text="Hi there. Looks good."),
        idempotency_key=IdempotencyKey(key="k1longenough"),
    )
    o.approve("tester", reason="manual")
    assert o.status == OutreachStatus.APPROVED
    o.mark_sent(123)
    assert o.status == OutreachStatus.SENT
    assert o.sent_message_id == 123
