"""LLM JSON parser tests."""
from __future__ import annotations

import pytest

from telegram_outreach.domain.exceptions import LLMContractError
from telegram_outreach.infrastructure.llm.parser import extract_json


def test_extract_json_direct() -> None:
    raw = '{"is_vacancy": true, "score": 0.5}'
    out = extract_json(raw)
    assert out["is_vacancy"] is True
    assert out["score"] == 0.5


def test_extract_json_fenced() -> None:
    raw = '```json\n{"x": 1}\n```'
    out = extract_json(raw)
    assert out["x"] == 1


def test_extract_json_with_prose() -> None:
    raw = 'Here is the answer: {"k": "v"} thanks!'
    out = extract_json(raw)
    assert out["k"] == "v"


def test_extract_json_fails() -> None:
    with pytest.raises(LLMContractError):
        extract_json("no json here")
    with pytest.raises(LLMContractError):
        extract_json("")
    with pytest.raises(LLMContractError):
        extract_json("[1, 2, 3]")  # not a dict
