"""Value object tests."""
from __future__ import annotations

import pytest

from telegram_outreach.domain.exceptions import MessageValidationError
from telegram_outreach.domain.value_objects import (
    ContactIdentifier,
    IdempotencyKey,
    MessageBody,
    RelevanceScore,
)


def test_relevance_score_bounds() -> None:
    with pytest.raises(ValueError):
        RelevanceScore(value=1.1)
    with pytest.raises(ValueError):
        RelevanceScore(value=-0.1)
    s = RelevanceScore(value=0.5)
    assert float(s) == 0.5


def test_message_body_validation() -> None:
    body = MessageBody(text="Hello. World.")
    body.validate()  # 2 sentences, ok
    assert body.sentence_count == 2

    too_short = MessageBody(text="hi")
    with pytest.raises(MessageValidationError):
        too_short.validate()

    too_long = MessageBody(text="One. " * 20)
    with pytest.raises(MessageValidationError):
        too_long.validate()


def test_message_body_forbidden_phrases() -> None:
    bad = MessageBody(text="Это лучший вариант. Скидка внутри.")
    with pytest.raises(MessageValidationError):
        bad.validate()
    assert "лучший" in bad.contains_forbidden()


def test_idempotency_key_deterministic() -> None:
    k1 = IdempotencyKey.build("outreach", ["v1", "c1", "x"])
    k2 = IdempotencyKey.build("outreach", ["v1", "c1", "x"])
    k3 = IdempotencyKey.build("outreach", ["v1", "c1", "y"])
    assert k1.key == k2.key
    assert k1.key != k3.key


def test_contact_identifier_normalises_username() -> None:
    ident = ContactIdentifier(user_id=1, username="@Foo_Bar")
    assert ident.username == "foo_bar"
    assert ident.is_resolved()


def test_contact_identifier_not_resolved() -> None:
    ident = ContactIdentifier()
    assert not ident.is_resolved()
