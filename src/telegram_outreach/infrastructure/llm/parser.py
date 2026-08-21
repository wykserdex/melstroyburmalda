"""Robust JSON parsing for LLM outputs.

LLMs sometimes emit:
- markdown fences ```json ... ```
- leading/trailing prose
- trailing commas
- single quotes

This module extracts and validates JSON, with bounded retries via the
caller (we don't loop here — caller decides policy).
"""
from __future__ import annotations

import json
import re
from typing import Any

from ...domain.exceptions import LLMContractError

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def extract_json(text: str) -> dict[str, Any]:
    """Try to find a JSON object in the text. Raise LLMContractError on failure."""
    if not text or not text.strip():
        raise LLMContractError("empty LLM response")
    text = text.strip()

    # 1) Try direct parse.
    try:
        return _coerce_dict(json.loads(text))
    except json.JSONDecodeError:
        pass

    # 2) Try a fenced code block.
    m = _FENCE.search(text)
    if m:
        try:
            return _coerce_dict(json.loads(m.group(1)))
        except json.JSONDecodeError:
            pass

    # 3) Brute-force: find first { and last }.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        snippet = text[start : end + 1]
        # Mild cleanup.
        snippet = snippet.replace("\u201c", '"').replace("\u201d", '"')
        try:
            return _coerce_dict(json.loads(snippet))
        except json.JSONDecodeError:
            pass

    raise LLMContractError(f"could not extract JSON from LLM response: {text[:200]!r}")


def _coerce_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LLMContractError(f"LLM response is not a JSON object: {type(value).__name__}")
    return value
